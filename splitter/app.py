import pyramid.config
import pyramid.view

def main(global_config, **settings):
    settings.setdefault("static_prefix", "/static")
    config = pyramid.config.Configurator(settings=settings)

    config.include("pyramid_jinja2")
    config.add_jinja2_search_path("splitter:templates")
    config.add_static_view(name="static", path="splitter:static")

    config.add_route("home", pattern="/")
    config.scan(__name__)

    return config.make_wsgi_app()



@pyramid.view.view_config(
    route_name="home",
    renderer="string",
)
def home(request):
    return "Home"
