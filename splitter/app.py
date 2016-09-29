import json
import pkg_resources
import httplib2
import io

import pyramid.config
import pyramid.view
import pyramid.httpexceptions
import pyramid.session

import apiclient.discovery
import apiclient.http
import oauth2client.client
import oauth2client.file


def main(global_config, **settings):
    settings.setdefault("static_prefix", "/static")
    session_factory = pyramid.session.SignedCookieSessionFactory(settings["cookie_secret"])
    config = pyramid.config.Configurator(settings=settings, session_factory=session_factory)

    config.include("pyramid_jinja2")
    config.add_jinja2_search_path("splitter:templates")
    config.add_static_view(name="static", path="splitter:static")

    def google_credentials(request):
        # Not in repo because... well it is a CREDENTIAL!!!
        return json.loads(pkg_resources.resource_string(__name__, "card_split_credentials.json"))

    config.add_request_method(google_credentials, property=True, reify=True)
    config.add_tween("splitter.app.tween")

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
            request.google_credentials["web"]["client_id"],
            request.google_credentials["web"]["client_secret"],
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
        {"name": "Test file", "id": "1oc-T9KDIw6-XncgL0p3ut3VLdiKa2fwyQ6d03o-D1sI"}
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
    lecture_html = get_lecture(request.credentials, request.matchdict["lecture_id"])
    return {
        "id": request.matchdict["lecture_id"],
        "html": lecture_html,
        "cards": []
    }


@pyramid.view.view_config(
    route_name="preview",
)
def preview(request):
    lecture_html = get_lecture(request.credentials, request.matchdict["lecture_id"])
    request.response.text = unicode(lecture_html)
    return request.response


def get_lecture(credentials, file_id):
    service = apiclient.discovery.build("drive", "v3", http=credentials.authorize(httplib2.Http()))
    resource = service.files().export(fileId=file_id, mimeType="text/html")
    fh = io.BytesIO()
    downloader = apiclient.http.MediaIoBaseDownload(fh, resource)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return fh.getvalue()
