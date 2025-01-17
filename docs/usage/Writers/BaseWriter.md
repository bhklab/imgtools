# Abstract Base Writer

The `AbstractBaseWriter` class is the foundation for all writers in this library.

It provides a standard interface, reusable methods, and tools that writers can extend
to handle file writing tasks efficiently and consistently.

If you’re building a writer to manage file outputs with custom paths, filenames, or formats,
this is where you start!

## Introduction

### What is the `AbstractBaseWriter`?

- Abstract base class for managing file-writing tasks.  
- Handles directories, filenames, and existing file scenarios.  
- Provides reusable methods for context management and logging.  
- Cannot be used directly – meant to be extended with your custom logic.  

### When Should you extend `AbstractBaseWriter` for your custom writer?

If you write many files with dynamic paths and filenames, or need
to manage file existence scenarios, you might consider extending `AbstractBaseWriter`
(or even one of its subclasses) to simplify your implementation.

`AbstractBaseWriter` is useful when you need:

- Dynamic paths and filenames based on placeholders like `{subject_id}`.  
- Control over what happens when files already exist (overwrite, skip, etc.).  
- Easy logging of saved files with an optional CSV index.  
- A consistent interface across different types of writers.  

---

## Core Concepts

### Root Directory and Filename Format

**Root Directory**:

- The base folder where all files will be written.  
- Automatically created if it doesn’t exist (configurable).  
- Example: `/data/outputs`.

**Filename Format**:

- A string template defining your file and folder names.  
- Uses placeholders like `{key}` to insert context values dynamically.  
- Example: `"{subject_id}/{date}_{session}.txt"` becomes `1234/2025-01-01_A.txt`.  

### File Existence Modes

Control what happens if the file already exists:  

- **`OVERWRITE`**: Delete and replace the file.  
- **`SKIP`**: Skip writing and return `None`.  
- **`FAIL`**: Raise an error if the file exists.  
- **`RAISE_WARNING`**: Log a warning and proceed with saving.  

### Context Management

In basic usage, users can pass in the context information as keyword arguments to each
`save()` call. However, the `AbstractBaseWriter` also provides a `set_context()` method
that allows you to set the context once and then call `save()` without passing in the context
again, or allowing to update specific context variables as needed.

**Context Variables**:

- A dictionary of key-value pairs used to resolve placeholders in the filename.  
- Example: `{"subject_id": "1234", "date": "2025-01-01"}`.  
- Set via `set_context()` or passed directly to methods like `save()`.

**Dynamic Updates**:  

- Context can be updated as needed for different files in a batch.  

### Index File Management

**What is the Index File?**:

- A CSV file used to log details about saved files, like their paths and context variables.  
- Helps track what files have been written, especially useful in batch operations.  

**How It Works**:

- By default, the index file is named `index.csv` and is stored in the root directory.  
- You can customize the filename or provide an absolute path for more control.  

**Key Features**:

- Automatically appends new entries for each saved file.  
- Uses inter-process locking to prevent conflicts in multi-threaded environments.  
- Includes context variables for each file, ensuring traceability.

### Sanitizing Filenames

**Why Sanitize Filenames?**:

- To ensure that filenames are safe and compatible across different operating systems.  

**How It Works**:

- Replaces illegal characters (e.g., `<`, `>`, `:`, `"`, `/`, `\`, `|`, `?`, `*`) with underscores.  
- Trims leading or trailing spaces and periods to avoid issues.  

**When Is It Applied?**:

- Automatically applied when generating filenames, unless disabled by setting `sanitize_filenames=False`.

### Multiprocessing Compatibility

**Why It Matters**:

- In batch operations or high-performance use cases, multiple processes may write files simultaneously.  

**Key Features**:

- Supports multiprocessing with inter-process locking to ensure thread-safe file writes.  
- Avoids conflicts or data corruption when multiple instances of a writer are running.

### Lifecycle Management

**Context Manager Support**:

- Writers can be used with `with` statements to ensure proper setup and cleanup.  

**What Happens on Exit?**:

- Removes lock files used for the index file.  
- Deletes empty directories created during the writing process (if no files were written).  

Example:

```python
with ExampleWriter(root_directory="/data", filename_format="{id}.txt") as writer:
  data = "Hello, World!"
  writer.save(data, id="1234")
```
