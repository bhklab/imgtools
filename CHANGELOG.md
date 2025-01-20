# CHANGELOG


## v1.15.0 (2025-01-17)

### Features

- Refactor io module, introduce new abstract base writer
  ([#181](https://github.com/bhklab/med-imagetools/pull/181),
  [`e04008d`](https://github.com/bhklab/med-imagetools/commit/e04008d2f2a2040f3a1092debca0c69caa180f85))

Co-authored-by: coderabbitai[bot] <136622811+coderabbitai[bot]@users.noreply.github.com>


## v1.14.0 (2025-01-17)

### Features

- Add dockerfile and update lockfile ([#177](https://github.com/bhklab/med-imagetools/pull/177),
  [`6cf5515`](https://github.com/bhklab/med-imagetools/commit/6cf551529ebb7bfb432d868f4859c0631ec413a8))


## v1.13.0 (2025-01-16)

### Features

- Refactor utility modules, add patternresolver, formt
  ([#170](https://github.com/bhklab/med-imagetools/pull/170),
  [`dcc5aad`](https://github.com/bhklab/med-imagetools/commit/dcc5aadc9c053e581877b7561828a97c0de122ec))

Introduce image utilities and a new PatternResolver class, along with updated dependencies and
  configuration adjustments. This enhances the project's capabilities for handling image processing
  and pattern resolution.

## Release Notes

- **New Features** - Added `PatternResolver` for parsing and resolving filename patterns. - Enhanced
  `ImageGeometry` with a spacing attribute. - Introduced a new method to extract ROI names from
  DICOM files.

- **Improvements** - Updated dependency specifications for numpy, pandas, and rich. - Improved code
  formatting across multiple files. - Expanded linting coverage for additional Python files. -
  Enhanced error handling and flexibility in ROI extraction from DICOM files.

- **Documentation** - Improved docstrings and code comments for better readability.

- **Chores** - Updated CI/CD workflow to support additional branches. - Reformatted configuration
  files for consistency. - Removed unused import from the `io` module. - Deleted the `common.py`
  file, removing obsolete functionality.


## v1.12.0 (2025-01-15)

### Features

- Improve structureset and crawl modules, Refactor tests and improve dataset handling
  ([#165](https://github.com/bhklab/med-imagetools/pull/165),
  [`5333a80`](https://github.com/bhklab/med-imagetools/commit/5333a80c6b2242c12d384846a3649a94a9eea60f))


## v1.11.2 (2025-01-15)

### Bug Fixes

- Replaced capturing regex terms with non capturing in datagraph
  ([#162](https://github.com/bhklab/med-imagetools/pull/162),
  [`3237b21`](https://github.com/bhklab/med-imagetools/commit/3237b21957adc5bc3efffe42d589bdeb4f27bc57))


## v1.11.1 (2025-01-11)

### Bug Fixes

- Rounding error in resample function ([#163](https://github.com/bhklab/med-imagetools/pull/163),
  [`f57a747`](https://github.com/bhklab/med-imagetools/commit/f57a7473b2dd5e14b12f4cdd833b9ecc1b60e6ad))

When output_size was not provided to `resample` function, the size was determined based on the
  spacing but was floored. This would sometimes incorrectly shrink the image size. Changed to use
  `np.round` instead.

Additionally, added the `output_size` argument to the `resample` call in the `resize` function. The
  output size is already available in the function as `new_size`, so it doesn't make sense to
  recalculate it in the `resample` function.

<!-- This is an auto-generated comment: release notes by coderabbit.ai -->

## Summary by CodeRabbit

- **Bug Fixes** - Improved image resampling and resizing functions with more precise rounding and
  type handling. - Enhanced parameter validation to ensure consistent integer conversion.

<!-- end of auto-generated comment: release notes by coderabbit.ai -->


## v1.11.0 (2025-01-02)

### Features

- Minor grade refactoring ([#158](https://github.com/bhklab/med-imagetools/pull/158),
  [`0dff0f4`](https://github.com/bhklab/med-imagetools/commit/0dff0f403d802d517614105b50f1c4008945e32d))

Co-authored-by: Joshua Siraj <joshua.siraj@ryerson.ca>

### Refactoring

- Improve logging, logic, and type annotations
  ([#151](https://github.com/bhklab/med-imagetools/pull/151),
  [`ef4d0e7`](https://github.com/bhklab/med-imagetools/commit/ef4d0e7c8f6b5e52c395916d0235645517a7ca03))

- **New Features** - Enhanced logging flexibility with new parameters for specifying logger names. -
  Improved progress reporting in the folder crawling process with descriptive progress bars.

- **Bug Fixes** - Updated error handling for invalid file actions and DICOM tag checks for clearer
  user feedback.

- **Documentation** 	- Improved docstring clarity and formatting across multiple functions.

- **Refactor** 	- Streamlined configuration files for testing and linting processes. - Restructured
  class and function definitions for better readability and maintainability.

- **Style** 	- Consistent formatting applied to function signatures and docstrings.

- Modules/datagraph.py ([#153](https://github.com/bhklab/med-imagetools/pull/153),
  [`41a7c88`](https://github.com/bhklab/med-imagetools/commit/41a7c88992525c8cdfd690ef287ab5f76dc8e588))


## v1.10.1 (2024-12-03)

### Bug Fixes

- Update .gitignore to exclude SQLite and database files
  ([`95a2179`](https://github.com/bhklab/med-imagetools/commit/95a217913798b2f1f4aa2555f1f8fddc65b5b44d))


## v1.10.0 (2024-12-03)

### Features

- Begin indexing database, update find-dicoms cli, add cli documentation
  ([#148](https://github.com/bhklab/med-imagetools/pull/148),
  [`48598e7`](https://github.com/bhklab/med-imagetools/commit/48598e7206c14bcd856e8a64b41cb88369647454))

## Release Notes

- **New Features** - Enhanced `find_dicoms` function to support limiting results and filtering by
  search input.

- **Documentation** - Updated installation instructions and expanded "Getting Started" section in
  the README. - Improved navigation structure in documentation, adding new entries for CLI
  reference.

- **Bug Fixes** - Streamlined error handling and logging for various functions, ensuring clearer
  outputs and improved functionality.

- **Chores** - Updated dependencies and configuration files for better management and performance.


## v1.9.4 (2024-11-29)

### Bug Fixes

- Configure Git credentials for GitHub Actions and update documentation deployment step
  ([`adf4e04`](https://github.com/bhklab/med-imagetools/commit/adf4e0431533d7434780951edd6ec82737cac21e))

- Update GitHub Actions workflow for concurrency and permissions;
  ([`45cddb4`](https://github.com/bhklab/med-imagetools/commit/45cddb4fd65be0df14a7f9d2a28261c5cc36159b))


## v1.9.3 (2024-11-29)

### Bug Fixes

- Improve logging maintainability and temporarily remove json logging configuration
  ([#146](https://github.com/bhklab/med-imagetools/pull/146),
  [`afdcc98`](https://github.com/bhklab/med-imagetools/commit/afdcc98a6f3fbd9e26da579fa39b37de7dbfd600))

Refactor logging code for improved maintainability by temporarily removing JSON logging
  functionality.

Update the .gitignore to exclude .dcm and .sqlite files.

Introduce an environment variable for debug logging and set the default log level based on this
  variable.

## Summary by CodeRabbit

- **New Features** - Introduced a new `LoggingManager` class for structured logging management. -
  Added support for JSON logging configuration (currently commented out). - Added a new environment
  variable for logging level configuration in development. 	- New entries in `.gitignore` to ignore
  `.dcm` and `.sqlite` files. - Enhanced CI/CD pipeline with new jobs for building and publishing
  documentation.

- **Improvements** - Enhanced logging control by utilizing environment variables for log levels. -
  Updated logging directory structure and default log filename for better organization. 	- Improved
  management of logging levels based on verbosity settings.

- **Bug Fixes** - Improved handling of logging level discrepancies with user-specified settings.

- **Documentation** - Updated docstrings and comments for clarity on new logging setup and features.


## v1.9.2 (2024-11-22)

### Bug Fixes

- Pipeline entry no longer needs to manually configure loglevel
  ([`66f8119`](https://github.com/bhklab/med-imagetools/commit/66f8119e6e2e1356c1e3b154e7ad2143cb77ea52))

### Chores

- **deps**: Update med-imagetools to version 1.9.1 and update sha256 checksum
  ([`ab77c58`](https://github.com/bhklab/med-imagetools/commit/ab77c5887e5bb8ae1fa477d2780b94dcdf3297a6))

### Refactoring

- **logging**: Simplify logger configuration and enhance environment variable handling
  ([`c1f624b`](https://github.com/bhklab/med-imagetools/commit/c1f624b7dc14d85176d97bf22918fb2f49dc4a8b))


## v1.9.1 (2024-11-22)

### Bug Fixes

- Downstream bug where datagraph.py was missing from wheel due to data* being ignored in .gitignore
  ([`2dbb245`](https://github.com/bhklab/med-imagetools/commit/2dbb2455e1edcbf663effd8d40b6bff88dc92082))

### Documentation

- Fix broken images
  ([`a7d0e3a`](https://github.com/bhklab/med-imagetools/commit/a7d0e3a70959e9a754efcade9f9f3aa75206c9ad))


## v1.9.0 (2024-11-22)

### Features

- Dicom-finder cli tool, and improve documentation
  ([#142](https://github.com/bhklab/med-imagetools/pull/142),
  [`2981baa`](https://github.com/bhklab/med-imagetools/commit/2981baac719da97d6ec6c3c444c046389d44baf3))

* docs: add mkdocs-include-markdown plugin for Markdown file inclusion

* docs: add tag helpers documentation for DICOM utilities

* docs: add documentation for finding DICOM files

* Update src/imgtools/cli/dicomfind.py

* feat: add regex filtering and improved logging for dicom_finder function

* chore: exclude CLI files from coverage reporting


## v1.8.2 (2024-11-21)

### Bug Fixes

- Update README with new CLI point and reorganize, and formatting
  ([`96c6ab6`](https://github.com/bhklab/med-imagetools/commit/96c6ab60488f97ee3830c7d4be8f96f1ebad0cac))


## v1.8.1 (2024-11-21)

### Bug Fixes

- Common prefix for tree
  ([`a940969`](https://github.com/bhklab/med-imagetools/commit/a94096910b3b95629e96e809ec21a705505fe841))


## v1.8.0 (2024-11-21)

### Features

- Add dicomsorting cli entry
  ([`d435f93`](https://github.com/bhklab/med-imagetools/commit/d435f93f0f2fda67094e4aeaa8a1828a570c534d))


## v1.7.0 (2024-11-19)

### Features

- Implement logging and some standards for ruff config
  ([#134](https://github.com/bhklab/med-imagetools/pull/134),
  [`7c31019`](https://github.com/bhklab/med-imagetools/commit/7c310196f87e4e3ba8503d12c45f799c831954e1))

* feat(logging): add structlog integration with custom processors and example logger

* chore: remove star imports

* feat(lint): update ruff configuration to include new linting rules and extend exclusions

* refactor: update pixi.lock and pixi.toml for ruff command structure and remove unused betapipeline
  entry

* refactor(logging): standardize string quotes and improve logger configuration handling

* feat(logging): integrate structured logging and enhance debug information in AutoPipeline and
  StructureSet

* fix: https://github.com/bhklab/med-imagetools/pull/134#discussion_r1846958744

* fix: https://github.com/bhklab/med-imagetools/pull/134#discussion_r1846958749

* fix: https://github.com/bhklab/med-imagetools/pull/134#discussion_r1846958747

* refactor(logging): streamline logging configuration and ensure log directory creation

* chore: add log files to .gitignore to prevent tracking of generated logs

* fix: Update src/imgtools/logging/__init__.py

Co-authored-by: coderabbitai[bot] <136622811+coderabbitai[bot]@users.noreply.github.com>

* fix: https://github.com/bhklab/med-imagetools/pull/134#discussion_r1847024952

* chore: update .gitignore to include log files in imgtools directory

* feat(datagraph): integrate logging for edge table processing and visualization

* feat(ops): add timing for graph formation and update DataGraph initialization

* chore: rename workflow from Test to CI-CD and restrict push triggers to main branch

* feat(crawl): integrate logging for folder crawling and data saving processes

* fix(structureset): enhance logging for ROI point retrieval errors

* fix(autopipeline): update logger level to use environment variable for flexibility

* fix(logging): streamline error handling for log directory creation

* fix: https://github.com/bhklab/med-imagetools/pull/134#discussion_r1847278305

* refactor(logging): enhance logging configuration and streamline JSON setup

* chore(pixi.lock): add license_family field for clarity

* refactor(logging): enhance LoggingManager with valid log levels and improve JSON logging setup

* refactor(logging): enhance documentation and improve LoggingManager configuration options

* refactor(logging): validate log level assignment before setting self.level

* feat(logging): add mypy and type-checking support; refactor logging manager and improve error
  handling

* refactor(logging): remove unused Optional import from typing

---------


## v1.6.0 (2024-11-15)

### Features

- Transfer project management to Pixi ([#133](https://github.com/bhklab/med-imagetools/pull/133),
  [`a268211`](https://github.com/bhklab/med-imagetools/commit/a26821164b55579aa42e87c28386db6c9398f2d6))

* feat: started port to pixi

* feat: updated test suite for pixi and started refactor of cicd

* build: added coverage to gha

* fix: explicitly direct location of package code and update pixi in pipeline

* fix: added linux to pixi

* chore: update GitHub Actions workflow for improved deployment process

* chore: clean up GitHub Actions workflow by removing commented-out jobs and updating dependencies

* chore: update GitHub Actions workflow to deploy from both main and devel branches, and refresh
  dependencies in pixi.lock

* chore(sem-ver): 1.6.0-rc.1

* fix: update version_toml path in pyproject.toml for semantic release

* chore(sem-ver): 1.6.0-rc.2

* chore: remove requirements.txt file and poetry.lock

* chore: update authors and maintainers in pyproject.toml, and add __version__ in __init__.py

* chore: remove setup.py file as part of project restructuring

* chore: update pixi.lock and add ruff configuration for linting

* chore: fix some recommendations from coderabbit

---------

Co-authored-by: semantic-release <semantic-release>


## v1.5.8 (2024-10-25)

### Bug Fixes

- **datagraph**: Iteration through edge_types wasnt updated for seg
  ([#131](https://github.com/bhklab/med-imagetools/pull/131),
  [`e7cca2a`](https://github.com/bhklab/med-imagetools/commit/e7cca2a8a2542e6f82ddae221b298094ebf3c022))

* fix(datagraph): update edge_types to 8 and handle new edge type for SEG->CT/MR mapping in final
  dataframe processing

* fix(pyproject): update attrs version constraint to allow all 23.x versions and above


## v1.5.7 (2024-10-23)

### Bug Fixes

- Ci-cd - add id in release for pypi step
  ([`7abd175`](https://github.com/bhklab/med-imagetools/commit/7abd175d58894b5ea84448735c4933de4aa156bd))


## v1.5.6 (2024-10-23)

### Bug Fixes

- Update ci to release to pypi
  ([`a92a41f`](https://github.com/bhklab/med-imagetools/commit/a92a41f56ab6d86c68d7657104f8c559b1958ffc))


## v1.5.5 (2024-10-23)

### Bug Fixes

- Remove deprecated pydicom.dicomdir.DicomDir variable type option
  ([#130](https://github.com/bhklab/med-imagetools/pull/130),
  [`56ef37e`](https://github.com/bhklab/med-imagetools/commit/56ef37e492d9a4f287ed9ecb7a1c968caca29726))

* fix: remove deprecated pydicom.dicomdir.DicomDir variable type option

* style: removed Union since dicom_data can only be a FileDataset

* refactor: remove Union import for linting

- Update ci to use semver bot
  ([`98e3bd0`](https://github.com/bhklab/med-imagetools/commit/98e3bd0c93fc2be20c31976092047e7a11db57fb))

### Chores

- #126 update docstring for StructureSetToSegmentation (reopen)
  ([#128](https://github.com/bhklab/med-imagetools/pull/128),
  [`272078c`](https://github.com/bhklab/med-imagetools/commit/272078c937fa62fee20a700150f2ed4da7458720))

* chore: bump artifact action version

* refactor: update StructureSetToSegmentation docstring and remove unused dev group in
  pyproject.toml

* chore: fix download action in workflow to use correct artifact version

* chore: correct instantiation reference and update parameter description in
  StructureSetToSegmentation docstring

* chore: enhance StructureSetToSegmentation docstring to support None as a roi_names option for
  loading all ROIs


## v1.5.4 (2024-06-12)

### Bug Fixes

- License updated to MIT ([#119](https://github.com/bhklab/med-imagetools/pull/119),
  [`6e755dd`](https://github.com/bhklab/med-imagetools/commit/6e755ddc70738da5c7afbced6e061d4e039fbd5f))


## v1.5.3 (2024-06-10)

### Bug Fixes

- Clarified license in README.md ([#118](https://github.com/bhklab/med-imagetools/pull/118),
  [`a4899ca`](https://github.com/bhklab/med-imagetools/commit/a4899ca15924dc9fa19f2e1f3964b7bd6c2e2d35))


## v1.5.2 (2024-05-29)

### Bug Fixes

- Upload latest version to pypi
  ([`1debad3`](https://github.com/bhklab/med-imagetools/commit/1debad3836732faf1a2e3f992a9f1d76943b076e))


## v1.5.1 (2024-05-29)

### Bug Fixes

- Format toml
  ([`269f55d`](https://github.com/bhklab/med-imagetools/commit/269f55db58322dc31a5c44ee5a5e2eb830ed3e4f))


## v1.5.0 (2024-05-29)

### Features

- Update Lock
  ([`26590a0`](https://github.com/bhklab/med-imagetools/commit/26590a09f71c9f797d89f6276aef1c1e416f77dc))

- Update readme
  ([`7cd808e`](https://github.com/bhklab/med-imagetools/commit/7cd808e954ce8e4e1bd8b3dbf1978ba70b0e6713))


## v1.1.0 (2024-05-29)

### Bug Fixes

- Add codecov badge
  ([`f43d042`](https://github.com/bhklab/med-imagetools/commit/f43d04231c76313d86d9e0444a6f1e26ed21b9fc))

- Explicit module to track for code coverage
  ([`f15d45d`](https://github.com/bhklab/med-imagetools/commit/f15d45dd43ef2d8956c0e7cbc91eb7741e9830e3))

### Chores

- Bump version
  ([`58ec67f`](https://github.com/bhklab/med-imagetools/commit/58ec67f1f83eeb1f1ce1b580818f5812e1d04244))

### Features

- Semantic release ([#114](https://github.com/bhklab/med-imagetools/pull/114),
  [`23a2d70`](https://github.com/bhklab/med-imagetools/commit/23a2d700772449837672d671873f9db3c544cd37))

* feat: semantic release

* fix: if statement issue


## v1.0.3 (2022-10-14)
