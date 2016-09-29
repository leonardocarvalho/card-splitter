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

    config.add_route("home", pattern="/")
    config.scan(__name__)

    return config.make_wsgi_app()


@pyramid.view.view_config(
    route_name="home",
)
def home(request):
    credentials = auth_credentials(request)
    http = credentials.authorize(httplib2.Http())
    service = apiclient.discovery.build("drive", "v3", http=http)

    resource = service.files().export(fileId="1oc-T9KDIw6-XncgL0p3ut3VLdiKa2fwyQ6d03o-D1sI",
                                      mimeType="text/html")
    fh = io.BytesIO()
    downloader = apiclient.http.MediaIoBaseDownload(fh, resource)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    request.response.text = unicode(fh.getvalue())
    return request.response


def auth_credentials(request):
    credentials = oauth2client.file.Storage("credential.dat").get()
    if credentials is not None and not credentials.invalid:
        return credentials

    flow = oauth2client.client.OAuth2WebServerFlow(
        request.google_credentials["web"]["client_id"],
        request.google_credentials["web"]["client_secret"],
        "https://www.googleapis.com/auth/drive",
        redirect_uri=request.route_url("home"),
    )

    user_code = request.params.get("code")
    if user_code:
        credentials = flow.step2_exchange(user_code)
        oauth2client.file.Storage("credential.dat").put(credentials)
        return credentials

    uri = flow.step1_get_authorize_url()
    raise pyramid.httpexceptions.HTTPFound(
        location=uri,
        headers={"Cache-Control": "no-cache"}
    )
