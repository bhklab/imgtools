name: manual-test

on: 
  workflow_dispatch:

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: [3.7, 3.8, 3.9]
      
    

    steps:
    - uses: actions/checkout@v2
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v2
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        python -m pip install flake8 pytest
        pip install -e .
        pip install -r requirements.txt
    - name: Import checking
      run: |
        python -c "import imgtools"
    - name: Run pytest
      run: |
        pytest tests