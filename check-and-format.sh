#!/bin/bash

set -ex

cd frontend
./check.sh
./format.sh
cd ../backend
./check.sh
./format.sh
