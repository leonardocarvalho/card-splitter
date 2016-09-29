import setuptools


setuptools.setup(
    name="card-splitter",
    version="1.0",
    packages=["splitter"],
    include_package_data=True,
    zip_safe=False,
    setup_requires=["setuptools_git==1.0b1"],
    install_requires=[
        "google-api-python-client",
        "pyramid",
        "pyramid_jinja2",
        "requests",
        "uwsgi",
    ],
    entry_points={
        "paste.app_factory": "main = splitter.app:main",
    },
)
