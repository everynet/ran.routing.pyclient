# Sphinx docs


### Generating api documentation

```bash
$ cd docs
$ sphinx-apidoc --separate -o ./source ../ran
```


### Cleaning api-docs

```bash
$ cd docs
$ rm source/ran.* source/modules.rst   
```


### Building docs

Please, use `poetry run` to ensure all required PATH variables are set, and sphinx can find required packages

```bash
$ cd docs
$ poetry run make html  
```


### Serving docs locally

After building sources, you can serve it locally

```bash
$ cd docs
$ python -m http.server 8000 --directory ./build/html
```
