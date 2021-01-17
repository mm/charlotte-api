"""Tests on all Charlotte API routes."""

from datetime import datetime
import pytest
from src.model import db, Link, LinkSchema

link_schema = LinkSchema()

@pytest.mark.parametrize(('url', 'status_code'), (
    ('/api/user', 403),
    ('/api/links', 403),
    ('/api/links/1', 403),
    ('/api/user', 200),
    ('/api/links', 200),
    ('/api/links/1', 200)
))
def test_protected_endpoints(client, seed_data, url, status_code):
    """The API key grants access to any method allowed on any resource. If the
    key is incorrect, any resource should return a 403 error on accession.
    """
    user_id, api_key = seed_data
    headers = {'x-api-key': api_key}
    if status_code == 403:
        headers['x-api-key'] = ''
    rv = client.get(url, headers=headers)
    assert rv.status_code == status_code


def test_user(client, seed_data):
    """When /user is accessed, the current user for the provided API key should
    be outputted with the number of links, ID and name.
    """
    user_id, api_key = seed_data
    rv = client.get('/api/user', headers={'x-api-key': api_key})
    json_data = rv.get_json()
    assert rv.status_code == 200
    assert json_data == {'id': 1, 'links': 9, 'name': 'Matt'}


@pytest.mark.parametrize('url', [
    '/api/links?page=a&per_page=b',
    '/api/links?page=1&per_page=a',
    '/api/links?page=a&per_page=1'
])
def test_invalid_pagination_for_links(client, seed_data, url):
    """If a user accidentally puts a non-integer into the page or
    per_page parameters, warn them about that.
    """
    user_id, api_key = seed_data
    rv = client.get(url, headers={'x-api-key': api_key})
    json_data = rv.get_json()
    assert json_data['message'] == "The page and per_page parameters must be integers"


def test_links_response(client, seed_data):
    """A request to /links should give back the list of links, but
    also pagination info and total links.
    """
    user_id, api_key = seed_data
    rv = client.get('/api/links', headers={'x-api-key': api_key})
    json_data = rv.get_json()
    assert len(json_data['links']) == 9
    assert json_data['next_page'] is None
    assert json_data['per_page'] == 20
    assert json_data['page'] == 1
    assert json_data['total_links'] == 9
    assert json_data['total_pages'] == 1


@pytest.mark.parametrize(('url', 'page', 'per_page', 'next_page', 'total_pages'), (
    ('/api/links?page=1', 1, 20, None, 1),
    ('/api/links?page=1&per_page=4', 1, 4, 2, 3),
    ('/api/links?page=2&per_page=4', 2, 4, 3, 3)
))
def test_pagination(client, seed_data, url, page, per_page, next_page, total_pages):
    """Paginating on the /links endpoint should give appropriate
    pagination info depending on what was passed in via URL parameters.
    """
    user_id, api_key = seed_data
    rv = client.get(url, headers={'x-api-key': api_key})
    json_data = rv.get_json()
    assert json_data['page'] == page
    assert json_data['per_page'] == per_page
    assert json_data['next_page'] == next_page
    assert json_data['total_pages'] == total_pages


@pytest.mark.parametrize(('url', 'number_of_links'), (
    ('/api/links?show=all', 9),
    ('/api/links', 9),
    ('/api/links?show=read', 0),
    ('/api/links?show=unread', 9)
))
def test_show_switch(client, seed_data, url, number_of_links):
    """The `show` parameter should control whether unread (default), read or all
    links are shown.
    """
    user_id, api_key = seed_data
    rv = client.get(url, headers={'x-api-key': api_key})
    json_data = rv.get_json()
    assert len(json_data['links']) == number_of_links


def test_link_get(client, app, seed_data):
    """GETing a link directly from /api/links/<int> should return a JSON
    response containing the date added, ID, read status, title and URL.
    """
    user_id, api_key = seed_data
    rv = client.get('/api/links/2', headers={'x-api-key': api_key})
    json_data = rv.get_json()
    with app.app_context():
        link = Link.query.get(2)
        assert link_schema.dump(link) == json_data


def test_link_post(client, seed_data):
    """POSTing a link to /api/links should return a 201 - Created status code. The
    Location HTTP header should correspond to the link where you can access the new resource.
    """
    user_id, api_key = seed_data
    body = {
        'title': 'Netflix',
        'url': 'https://www.netflix.com'
    }
    rv = client.post('/api/links', headers={'x-api-key': api_key}, json=body)
    json_data = rv.get_json()
    new_id = json_data['id']
    assert rv.status_code == 201
    assert rv.headers['Location'] == 'http://localhost/api/links/'+str(new_id)


@pytest.mark.parametrize(('url', 'title'), (
    ('https://www.microsoft.com/en-ca/', 'Microsoft - Official Home Page'),
    ('https://github.com', 'GitHub: Where the world builds software · GitHub')
))
def test_link_post_infer_title(client, seed_data, url, title):
    """POSTing a link without a title should cause the title of the URL to be
    inferred.
    """
    user_id, api_key = seed_data
    rv = client.post('/api/links', headers={'x-api-key': api_key}, json={'url': url})
    json_data = rv.get_json()
    assert rv.status_code == 201
    assert json_data['title'] == title


@pytest.mark.parametrize(('payload', 'status_code', 'validation_error'), (
    ({}, 422, 'Field may not be null.'),
    ({'url': 'frifh123'}, 422, 'Not a valid URL.'),
    ({'url': 'google'}, 422, 'Not a valid URL.'),
    ({'url': 'google.com'}, 422, 'Not a valid URL.')
))
def test_link_post_invalid_url(client, seed_data, payload, status_code, validation_error):
    """POSTing an empty JSON payload, or an invalid URL should yield a 422, and
    a descriptive validation error in issues.url.
    """
    user_id, api_key = seed_data
    rv = client.post('/api/links', headers={'x-api-key': api_key}, json=payload)
    json_data = rv.get_json()

    assert rv.status_code == status_code
    print(json_data['issues'])
    assert validation_error in json_data['issues']['url']


@pytest.mark.parametrize(('url', 'status_code', 'message'), (
    ('/api/links/6', 200, 'Link with ID 6 deleted successfully'),
    ('/api/links/100', 404, 'Requested resource was not found in the database')
))
def test_link_delete(client, seed_data, url, status_code, message):
    """Sending a DELETE request to /api/links/<int:id> should return a 200 if successful,
    and a message notifying the user that it was successful (or a 404 if not found)
    """
    user_id, api_key = seed_data
    rv = client.delete(url, headers={'x-api-key': api_key})
    assert rv.status_code == status_code
    assert rv.get_json().get('message') == message


@pytest.mark.parametrize(('id', 'payload', 'status_code', 'message'), (
    (1, {'read': True}, 200, 'Link with ID 1 updated successfully'),
    (2, {'read': True, 'title': 'Updated title'}, 200, 'Link with ID 2 updated successfully'),
    (2, None, 400, 'This method expects valid JSON data as the request body'),
    (2, {}, 200, 'Link with ID 2 updated successfully'),
    (10, {'read': True}, 404, 'Requested resource was not found in the database'),
    (3, {'url': 'hryufhryf'}, 422, 'The submitted data failed validation checks'),
    (3, {'url': None}, 422, 'The submitted data failed validation checks')
))
def test_link_patch(app, client, seed_data, id, payload, status_code, message):
    """Sending a PATCH request with a valid body and on a valid link should
    return a 200 if successful, and a message notifying the user that it was successful.
    An empty JSON payload should still yield a 200 (nothing was changed)
    """
    user_id, api_key = seed_data
    rv = client.patch('/api/links/'+str(id), headers={'x-api-key': api_key}, json=payload)

    assert rv.status_code == status_code
    assert rv.get_json().get('message') == message

    # Check whether our underlying object is actually updated (if we sent something valid)
    if rv.status_code == 200:
        with app.app_context():
            updated_link = Link.query.get(id)
            for key, value in payload.items():
                assert getattr(updated_link, key) == value
