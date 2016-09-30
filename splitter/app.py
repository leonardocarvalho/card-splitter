import httplib2
import io
import os

import pyramid.config
import pyramid.view
import pyramid.httpexceptions

import apiclient.discovery
import apiclient.http
import oauth2client.client
import oauth2client.file


def main(global_config, **settings):
    settings["google_client_id"] = os.getenv("CLIENT_ID")
    settings["google_client_secret"] = os.getenv("CLIENT_SECRET")
    settings["google_api_key"] = os.getenv("API_KEY")
    config = pyramid.config.Configurator(settings=settings)

    if os.getenv("AUTH", "false").lower() == "true":
        config.add_tween("splitter.app.tween")
    else:
        config.add_request_method(
            lambda request: None,
            property=True,
            reify=True,
            name="credentials",
        )

    config.add_route("lectures", pattern="/lectures")
    config.add_route("one_lecture", pattern="/lectures/{lecture_id}")
    config.add_route("preview", pattern="/lectures/{lecture_id}/preview")
    config.scan(__name__)

    return config.make_wsgi_app()


def tween(handler, registry):

    def authenticate_and_authorize(request):
        credentials = oauth2client.file.Storage("credential.dat").get()
        if credentials is not None and not credentials.invalid:
            request.credentials = credentials
            return handler(request)

        flow = oauth2client.client.OAuth2WebServerFlow(
            request.registry.settings["google_client_id"],
            request.registry.settings["google_client_secret"],
            "https://www.googleapis.com/auth/drive",
            redirect_uri=request.route_url("lectures"),
        )

        user_code = request.params.get("code")
        if user_code:
            credentials = flow.step2_exchange(user_code)
            oauth2client.file.Storage("credential.dat").put(credentials)
            request.credentials = credentials
            return handler(request)

        return pyramid.httpexceptions.HTTPFound(
            location=flow.step1_get_authorize_url(),
            headers={"Cache-Control": "no-cache"}
        )

    return authenticate_and_authorize


@pyramid.view.view_config(
    route_name="lectures",
    renderer="json",
)
def lectures(request):
    lectures = [
        {"name": "Test file", "id": "1oc-T9KDIw6-XncgL0p3ut3VLdiKa2fwyQ6d03o-D1sI"},
        {"name": "Public", "id": "1Hnoj8GTXo7CHUy3D-mfeoUYqjEFD7XwLvncKbkdkqao"},
    ]

    return [
        dict(
            lecture,
            lecture=request.route_url("one_lecture", lecture_id=lecture["id"]),
            preview=request.route_url("preview", lecture_id=lecture["id"]),
        )
        for lecture in lectures
    ]


@pyramid.view.view_config(
    route_name="one_lecture",
    renderer="json",
)
def one_lecture(request):
    lecture_html = get_lecture(request.matchdict["lecture_id"],
                               request.credentials,
                               request.registry.settings["google_api_key"])
    return {
        "id": request.matchdict["lecture_id"],
        "html": lecture_html,
        "cards": []
    }


@pyramid.view.view_config(
    route_name="preview",
)
def preview(request):
    lecture_html = get_lecture(request.matchdict["lecture_id"],
                               request.credentials,
                               request.registry.settings["google_api_key"])
    request.response.text = unicode(lecture_html)
    return request.response


def get_lecture(file_id, credentials=None, api_key=None):
    if credentials:
        http_auth = credentials.authorize(httplib2.Http())
        service = apiclient.discovery.build("drive", "v3", http=http_auth)
    else:
        service = apiclient.discovery.build("drive", "v3", developerKey=api_key)
    resource = service.files().export(fileId=file_id, mimeType="text/html")
    fh = io.BytesIO()
    downloader = apiclient.http.MediaIoBaseDownload(fh, resource)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return fh.getvalue()
