# Dockerfile for USGS Tetracorder Spectroscopy System

FROM ubuntu:22.04

LABEL description="USGS Tetracorder Spectroscopy System"
LABEL version="5.27"

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gfortran gcc g++ make ratfor bison flex \
    libx11-dev libxpm-dev libxt-dev \
    libpng-dev libjbig-dev libjbig0 libjbig2dec0 libjbig2dec0-dev jbigkit-bin \
    libjpeg-dev zlib1g zlib1g-dev \
    imagemagick netpbm inotify-tools \
    default-jdk vim tcsh csh gnuplot gnuplot-x11 wget curl git \
    && rm -rf /var/lib/apt/lists/*

# Create directory structure
RUN mkdir -p /home/t1 /home/sl1 /home/src/local /usr/spool/gplot \
    /usr/local/lib /usr/local/bin /usr/local/man/man1 \
    && chmod 777 /usr/spool/gplot \
    && touch /usr/spool/plot.log && chmod 666 /usr/spool/plot.log \
    && ln -sf /home/t1 /t1 && ln -sf /home/sl1 /sl1 && ln -sf /home/src /src

# Environment variables for specpr/tetracorder build
ENV LD_LIBRARY_PATH="/usr/local/lib:/usr/lib/x86_64-linux-gnu"
ENV LD_RUN_PATH="/usr/local/lib"
ENV SSPPFLAGS="LINUX -INTEL -XWIN"
ENV SPECPR="/src/local/specpr"
ENV RANDRET="32767"
ENV SP_LOCAL="/usr/local"
ENV SP_BIN="securebin"
ENV SP_LDFLAGS=" "
ENV SP_LDLIBS="-lX11"
ENV SPSDIR="syslinux"
ENV RANLIB="ranlib"
ENV SSPP="sspp"
ENV F77="gfortran"
ENV CC="cc"
ENV AR="ar"
ENV RF="ratfor"
ENV YACC="bison -y"
ENV LEX="flex"
ENV SP_FFLAGS="-C -O -m64"
ENV SP_FFLAGS1="-C -m64"
ENV SP_FFLAGS2="-C -m64"
ENV SPKLUDGE="LINUX"
ENV BSLASH="-fno-backslash"
ENV SP_FOPT="-O"
ENV SP_FOPT1="-O"
ENV SP_FOPT2="-O"
ENV SP_RFLAGS="<"
ENV SP_CFLAGS="-O -m64"
ENV SP_ARFLAGS="rv"
ENV SP_GFLAGS="-s"
ENV SP_LFLAGS=" "
ENV SP_YFLAGS=" "
ENV mcmodelflags="-mcmodel=medium"
# Missing environment variables that caused build failures
ENV SP_OBJ="/src/local/specpr/obj"
ENV SP_LIB="/src/local/specpr/lib"
ENV SPSYSOBJ="/src/local/specpr/obj/syslinux.o"
ENV LD="ld"

ENV PATH="/usr/local/bin:${PATH}"

WORKDIR /src/local

# Copy source code
COPY specpr /src/local/specpr
COPY tetracorder5.26 /src/local/tetracorder5.26
COPY tetracorder5.27 /src/local/tetracorder5.27
COPY sl1 /sl1
COPY tetracorder.cmds /t1/tetracorder.cmds
COPY cuprite95 /t1/cuprite95

# Create required directories for specpr build
RUN mkdir -p /src/local/specpr/obj /src/local/specpr/lib

# Step 1: Build and install sspp (specpr preprocessor) - required first
WORKDIR /src/local/specpr/src.sspp
RUN gcc -o sspp sspp.c strcmpn.c \
    && cp sspp /usr/local/bin/ \
    && chmod 755 /usr/local/bin/sspp

# Step 2: Install check_env utility
RUN cp /src/local/specpr/utility/check_env /usr/local/bin/ \
    && chmod 755 /usr/local/bin/check_env

# Step 3: Build specpr library (src.lib)
WORKDIR /src/local/specpr/src.lib
RUN make

# Step 4: Build syslinux component (contains recomp function)
WORKDIR /src/local/specpr/src.specpr/syslinux
RUN make

# Step 5: Build specpr main application
WORKDIR /src/local/specpr/src.specpr
RUN make && make install

# Step 6: Build additional specpr components
WORKDIR /src/local/specpr/src.sp_stamp
RUN make && make install || true

WORKDIR /src/local/specpr/src.spprint/SRC
RUN make && make install || true

WORKDIR /src/local/specpr/src.spsetwave/SRC
RUN make && make install || true

WORKDIR /src/local/specpr/src.spsettitle/SRC
RUN make && make install || true

WORKDIR /src/local/specpr/src.spratio2spectra/SRC
RUN make && make install || true

WORKDIR /src/local/specpr/src.spfeatures/SRC
RUN make && make install || true

WORKDIR /src/local/specpr/src.fstospecpr
RUN make && make install || true

WORKDIR /src/local/specpr/src.tgifdaemon
RUN make && make install || true

WORKDIR /src/local/specpr/src.psplotdaemon
RUN make && make install || true

WORKDIR /src/local/specpr/src.datatran/SRC.asciitosp
RUN make && make install || true

WORKDIR /src/local/specpr/src.datatran/SRC.sptoascii
RUN make && make install || true

WORKDIR /src/local/specpr/src.oceanopticstospecpr
RUN make && make install || true

# Copy specpr utilities
RUN for i in specpr dspecpr radtran dradtran spfind sp_spool rule \
    spedit fstospecpr-multiple logtetracorder specprhelp specprnt; do \
    cp /src/local/specpr/utility/$i /usr/local/bin/ 2>/dev/null || true; \
    done

RUN cp /src/local/specpr/utility-davinci/davinci.print.specpr.to.ascii /usr/local/bin/ 2>/dev/null || true

# Step 7: Build tetracorder 5.27 (single spectrum mode first)
# Use line numbers to precisely edit the correct parameter block (B block: lines 131-134)
# Comment out cube mode (A block: lines 124-127) and enable single spectrum mode (B block)
WORKDIR /src/local/tetracorder5.27
RUN sed -i '124s/^        parameter/#        parameter/' multmap.h \
    && sed -i '125s/^        parameter/#        parameter/' multmap.h \
    && sed -i '126s/^        parameter/#        parameter/' multmap.h \
    && sed -i '127s/^        parameter/#        parameter/' multmap.h \
    && sed -i '131s/^#        parameter/        parameter/' multmap.h \
    && sed -i '132s/^#        parameter/        parameter/' multmap.h \
    && sed -i '133s/^#        parameter/        parameter/' multmap.h \
    && sed -i '134s/^#        parameter/        parameter/' multmap.h \
    && echo "=== Single spectrum mode config ===" \
    && sed -n '124,134p' multmap.h \
    && make installsingle

# Step 8: Build tetracorder 5.27 (cube mode)
# Restore cube mode (A block: lines 124-127) and comment out single spectrum mode (B block)
RUN sed -i '131s/^        parameter/#        parameter/' multmap.h \
    && sed -i '132s/^        parameter/#        parameter/' multmap.h \
    && sed -i '133s/^        parameter/#        parameter/' multmap.h \
    && sed -i '134s/^        parameter/#        parameter/' multmap.h \
    && sed -i '124s/^#        parameter/        parameter/' multmap.h \
    && sed -i '125s/^#        parameter/        parameter/' multmap.h \
    && sed -i '126s/^#        parameter/        parameter/' multmap.h \
    && sed -i '127s/^#        parameter/        parameter/' multmap.h \
    && echo "=== Cube mode config ===" \
    && sed -n '124,134p' multmap.h \
    && rm -f *.o && make install

# Step 9: Build tetracorder 5.26
WORKDIR /src/local/tetracorder5.26
RUN make installsingle || true && rm -f *.o && make install || true

# Copy davinci wrappers
RUN cp -f /t1/tetracorder.cmds/tetracorder5.27f.cmds/davinci-cmds.for.usr.local.bin/* /usr/local/bin/ 2>/dev/null || true

RUN mkdir -p /data
WORKDIR /data

CMD ["/bin/bash"]
