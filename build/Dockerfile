FROM arm64v8/debian:bullseye

ENV DEBIAN_FRONTEND=noninteractive

# Install base tools and deps for Python build
RUN apt update && apt install -y \
    wget build-essential libssl-dev libbz2-dev libsqlite3-dev \
    liblzma-dev libreadline-dev libffi-dev \
    libctypes-ocaml-dev libcurses-ocaml-dev \
    dphys-swapfile lintian

# Copy build script and source files
COPY . /src
WORKDIR /src

# Run the build script
RUN chmod +x build/build-python.sh && ./build/build-python.sh
