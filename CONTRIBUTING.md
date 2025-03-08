## Packaging

```shell
rm -rf dist; python setup.py sdist bdist_wheel
cd plugins/auth       ; rm -rf dist && python setup.py sdist bdist_wheel ; cp dist/* ../../dist/ ; cd ../..
cd plugins/contents   ; rm -rf dist && python setup.py sdist bdist_wheel ; cp dist/* ../../dist/ ; cd ../..
cd plugins/lab        ; rm -rf dist && python setup.py sdist bdist_wheel ; cp dist/* ../../dist/ ; cd ../..
cd plugins/jupyterlab ; rm -rf dist && python setup.py sdist bdist_wheel ; cp dist/* ../../dist/ ; cd ../..
cd plugins/notebook   ; rm -rf dist && python setup.py sdist bdist_wheel ; cp dist/* ../../dist/ ; cd ../..
cd plugins/kernels    ; rm -rf dist && python setup.py sdist bdist_wheel ; cp dist/* ../../dist/ ; cd ../..
cd plugins/nbconvert  ; rm -rf dist && python setup.py sdist bdist_wheel ; cp dist/* ../../dist/ ; cd ../..
cd plugins/terminals  ; rm -rf dist && python setup.py sdist bdist_wheel ; cp dist/* ../../dist/ ; cd ../..
cd plugins/yjs        ; rm -rf dist && python setup.py sdist bdist_wheel ; cp dist/* ../../dist/ ; cd ../..

twine upload dist/*
```

## Running Tests

```shell
hatch run dev.jupyterlab-auth:test
```

## Linting

```shell
hatch run dev.jupyterlab-auth:lint
```
