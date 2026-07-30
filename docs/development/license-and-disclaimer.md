# License & disclaimer

## Status and authorship

This website documents integration work in the
[`autonlab/spectroscopy-tetracorder`](https://github.com/autonlab/spectroscopy-tetracorder)
fork. It is not the official Tetracorder documentation, and the maintainers of
this fork do not claim authorship of Tetracorder, Specpr, the expert systems,
or the upstream spectral libraries. References to the Planetary Science
Institute, USGS, NASA, instruments, missions, or upstream contributors identify
sources and context; they do not imply affiliation or endorsement.

The authoritative upstream project is
[`PSI-edu/spectroscopy-tetracorder`](https://github.com/PSI-edu/spectroscopy-tetracorder).

## Repository licenses and notices

The upstream repository's root
[`LICENSE`](https://github.com/PSI-edu/spectroscopy-tetracorder/blob/main/LICENSE)
contains the GNU General Public License version 3. Individual subtrees also
contain component-specific copyright, redistribution, source-availability,
no-endorsement, warranty, and liability notices. In particular, consult the
notices shipped with:

- [`tetracorder6.00`](https://github.com/PSI-edu/spectroscopy-tetracorder/blob/main/tetracorder6.00/license.txt);
- the [6.00 expert-system commands](https://github.com/PSI-edu/spectroscopy-tetracorder/blob/main/tetracorder.cmds/tetracorder6.00a.cmds/license.txt);
- [`specpr`](https://github.com/PSI-edu/spectroscopy-tetracorder/blob/main/specpr/license.txt); and
- the [USGS spectral-library tree](https://github.com/PSI-edu/spectroscopy-tetracorder/blob/main/sl1/usgs/library06/license.txt).

The library notice identifies USGS Spectral Library 06 data as public-domain
data while applying its component notice to related software. The root and
component license files are controlling; this page summarizes them and does
not replace, narrow, or expand their terms. Preserve those notices when
redistributing the corresponding material.

The documentation site is built with
[Material for MkDocs](https://github.com/squidfunk/mkdocs-material), and the
interactive spectrum plot loads
[Chart.js 4.5.1](https://github.com/chartjs/Chart.js/tree/v4.5.1) from jsDelivr.
Those projects remain subject to their own licenses and notices.

## Scientific and operational use

This wrapper is an interface to an existing expert system, not an independent
scientific validation of that system. Synthetic spectra and saved outputs in
the examples test execution and data plumbing; they are not certified mineral
identifications, calibration standards, or evidence of accuracy for a real
dataset.

Users are responsible for verifying instrument calibration, wavelength and
FWHM compatibility, preprocessing, reference-library suitability, expert-system
settings, output interpretation, and fitness for their intended use. Do not
base safety-critical, operational, regulatory, medical, legal, or financial
decisions solely on this software or documentation.

## Warranty and liability

The repository software and these working notes are provided as-is, without a
separate warranty or service commitment from the maintainers of this fork, to
the extent permitted by applicable law. The warranty disclaimers and liability
limitations in the controlling root and component licenses remain applicable.
For an institutional release, contractual deployment, or interpretation of
the mixed repository notices, consult qualified counsel rather than relying on
this summary.
