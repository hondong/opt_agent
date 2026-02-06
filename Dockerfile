# Use a slim Python image
FROM python:3.13-slim

# 1. Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget cmake gcc g++ m4 xz-utils libgmp-dev unzip \
    zlib1g-dev libboost-program-options-dev \
    libboost-serialization-dev libboost-regex-dev \
    libboost-iostreams-dev libtbb-dev libreadline-dev \
    pkg-config git liblapack-dev libgsl-dev flex bison \ 
    libcliquer-dev gfortran file dpkg-dev libopenblas-dev \
    rpm libmetis-dev

# Download the correct SCIP binary based on the architecture
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        wget https://scipopt.org/download/release/scipoptsuite_10.0.0-1+trixie_aarch64.deb -O scip.deb; \
    else \
        echo "CPU architecture not yet supported"; \
        exit 1; \
    fi


# 2. Install SCIP
RUN dpkg -X scip.deb /usr/local/ && mv /usr/local/usr /usr/local/scip && rm scip.deb

# # 3. CRITICAL: Point PySCIPOpt to the SCIP installation
ENV SCIPOPTDIR=/usr/local/scip

# # # 4. Now install the Python wrapper
RUN pip install --no-cache-dir pyscipopt

# Set the working directory
WORKDIR /home/opt_agent

# # # Copy requirements and install dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# # # Copy the rest of your code
COPY . .