# coding: utf-8
import httplib2
import io
import os
import re

import pyramid.config
import pyramid.view
import pyramid.httpexceptions
import pyramid.response

import apiclient.discovery
import apiclient.http
import oauth2client.client
import oauth2client.file


LECTURES = [
    {
        "id": "1N92p0DfRBmhWJ83njWqbmtYTbIvXeEvD7UKfgQJ_6sc",
        "title": u"Lima Barreto",
        "subject": u"Literatura",
    },
    {
        "id": "1rf4GQlnrI-siIRIEUalGBeTo1OH5zHw5KuJu3ye4jJY",
        "title": u"Progressão Aritmética II",
        "subject": u"Álgebra",
    },
    {
        "id": "1BLlYLJ6HyPzxOMdMSCFk6OSTFj1ezReAf2rA4fZ4fBg",
        "title": u"Briófitas",
        "subject": u"Biologia 2",
    },
    {
        "id": "1lOA5E9L9kDxzmQ8nY95C3a80Y8f-IDHYXAzi31_o2jE",
        "title": u"Brasil e Mercosul",
        "subject": u"Geografia",
    },
]


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

    def lectures(request):
        for lec in LECTURES:
            lec.update({"links": dict(
                lecture=request.route_url("one_lecture", lecture_id=lec["id"]),
                preview=request.route_url("preview", lecture_id=lec["id"]),
            )})
        return LECTURES

    config.add_request_method(lectures, property=True, reify=True)

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
    return request.lectures


@pyramid.view.view_config(
    route_name="one_lecture",
    renderer="json",
)
def one_lecture(request):
    lecture, = filter(lambda l: l["id"] == request.matchdict["lecture_id"], request.lectures)
    lecture_html = get_lecture(
        lecture["id"],
        request.credentials,
        request.registry.settings["google_api_key"]
    )
    only_dashes = lambda s: all(x == "-" for x in s)
    cards = filter(lambda s: not only_dashes(s), re.split("(-{5,10000})", lecture_html))
    return dict(lecture, html=lecture_html, cards=cards)


@pyramid.view.view_config(
    route_name="preview",
)
def preview(request):
    lecture_html = get_lecture(request.matchdict["lecture_id"],
                               request.credentials,
                               request.registry.settings["google_api_key"])
    return pyramid.response.Response(body=lecture_html, status=200)


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
    html = (unicode(fh.getvalue(), "utf-8")
            .replace("<html>", "")
            .replace("</html>", "")
            .replace("<body", "<div")
            .replace("</body>", "</div>"))
    return re.sub("<head.*?>.*</head>", "", html)
