# syntax=docker/dockerfile:1
#
# Entorno reproducible para correr el testbench RV32I con cocotb + Verilator.
#
#   docker build -t rv32i-cocotb .
#   docker run --rm -it -v "${PWD}:/work" rv32i-cocotb
#   (dentro del contenedor)  make test_cpu
#
# cocotb 2.x requiere Verilator >= 5.036; Ubuntu 24.04 solo trae 5.020 por apt,
# así que Verilator se compila desde el código fuente en una etapa aparte.
# Se puede cambiar la versión con:  docker build --build-arg VERILATOR_VERSION=v5.048 ...

ARG UBUNTU_VERSION=24.04

# ---------------------------------------------------------------------------
# Etapa 1: compilar Verilator
# ---------------------------------------------------------------------------
FROM ubuntu:${UBUNTU_VERSION} AS verilator-build

ARG VERILATOR_VERSION=v5.040
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git autoconf make g++ flex bison help2man perl python3 \
        libfl2 libfl-dev zlib1g zlib1g-dev ccache \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch ${VERILATOR_VERSION} \
        https://github.com/verilator/verilator.git /tmp/verilator \
    && cd /tmp/verilator \
    && autoconf \
    && ./configure --prefix=/opt/verilator \
    && make -j"$(nproc)" \
    && make install \
    && rm -rf /tmp/verilator

# ---------------------------------------------------------------------------
# Etapa 2: imagen final (Verilator + Python/cocotb + el repo)
# ---------------------------------------------------------------------------
FROM ubuntu:${UBUNTU_VERSION}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Lo que Verilator necesita en tiempo de ejecución para compilar el simulador
# (g++, make, perl, zlib) + Python + utilidades de trabajo.
# ccache es obligatorio: Verilator se configuró con ccache en la etapa 1 y los
# Makefiles que genera lo invocan siempre (además acelera las recompilaciones).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates make g++ perl zlib1g-dev ccache \
        python3 python3-venv python3-dev \
        git dos2unix less nano \
    && rm -rf /var/lib/apt/lists/*

COPY --from=verilator-build /opt/verilator /opt/verilator

# Entorno virtual de Python con las dependencias del repo.
RUN python3 -m venv /opt/venv
ENV PATH=/opt/verilator/bin:/opt/venv/bin:${PATH}

COPY cocotb/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Copia del repo dentro de la imagen (sirve si no se monta la carpeta).
# Se convierten finales de línea CRLF -> LF por si el repo viene de Windows.
WORKDIR /work
COPY . /work
RUN find /work -type f \( -name '*.py' -o -name '*.sv' -o -name '*.svh' -o -name '*.v' \
        -o -name '*.f' -o -name '*.ini' -o -name '*.txt' -o -name '*.md' -o -name 'Makefile' \) \
        -exec dos2unix -q {} + \
    && git config --system --add safe.directory '*'

# Comprobación rápida de las herramientas al construir la imagen.
RUN verilator --version && python -c "import cocotb; print('cocotb', cocotb.__version__)"

CMD ["bash"]
