#!/bin/bash
VERSION=${1:-v1.0}
docker compose build
docker tag cuentasmexico:latest luinmack/cuentasmexico:$VERSION
docker push luinmack/cuentasmexico:$VERSION