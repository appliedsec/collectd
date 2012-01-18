from setuptools import setup

setup(
    name = "collectd",
    version = "1.0.1",
    py_modules = ["collectd"],
    
    author = "Eli Courtwright",
    author_email = "eli@courtwright.org",
    description = "library for sending statistics over UDP to collectd servers",
    license = "BSD",
    url = "https://github.com/appliedsec/collectd",
    
    download_url = "http://collectd.googlecode.com/files/collectd-1.0.tar.gz",
    
    classifiers = [
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Logging",
        "Topic :: System :: Networking",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Networking :: Monitoring",
    ],
    
    long_description = """\
This Python module implements the binary protocol used by the collectd Network
plugin to let you send arbitrary numeric data to collectd servers. Other than
turning on the Network plugin on the destination collectd server, no
configuration is needed."""
)
