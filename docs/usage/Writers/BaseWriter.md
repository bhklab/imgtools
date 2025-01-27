# Abstract Base Writer

The `AbstractBaseWriter` class is the foundation for all writers in this library.

It provides a standard interface, reusable methods, and tools that writers can extend
to handle file writing tasks efficiently and consistently.

If you’re building a writer to manage file outputs with custom paths, filenames, or formats,
this is where you start!

For details on implementing the `AbstractBaseWriter` in your custom writer, see the
[Implementing Writers](./ImplementingWriters.md) guide.

## Introduction

### What is the `AbstractBaseWriter`?

The `AbstractBaseWriter` is:

- **A reusable template**: Manage file-writing tasks consistently across different writer implementations.  
- **Customizable**: Extend it to handle your file formats and workflows.  
- **Safe and robust**: Features context management, filename sanitization, and optional CSV indexing.  

### When Should you extend `AbstractBaseWriter` for your custom writer?

If you write many files with dynamic paths and filenames, or need
to manage file existence scenarios, you might consider extending `AbstractBaseWriter`
(or even one of its subclasses) to simplify your implementation.

`AbstractBaseWriter` is useful when you need:

- Dynamic paths and filenames (e.g., `{subject_id}/{study_date}.nii.gz`).  
- Configurable handling of existing files (`OVERWRITE`, `SKIP`, etc.).  
- Logging of saved files via an optional CSV index.  
- Thread-safe and multiprocessing-compatible file writing.  
- A consistent interface across different types of writers.  

---

## Core Concepts

### Root Directory and Filename Format Parameters

**Root Directory**:

- Base folder for all saved files, automatically created if missing (via `create_dirs` parameter)

**Filename Format**:

- A string template defining your file and folder names.  
- Uses placeholders like `{key}` to insert context values dynamically.  

Example:

```python
writer = ExampleWriter(
    root_directory="./data",
    filename_format="{person_name}/{date}_{message_type}.txt",
)

# Save a file with context variables
data = "Hello, World!"
writer.save(
  data, 
  person_name="JohnDoe",
  date="2025-01-01",
  message_type="greeting"
)

# Saved file path: 
# ./data/JohnDoe/2025-01-01_greeting.txt
```

### File Existence Modes

**Why It Matters**:

- When your writer saves a file, it needs to decide what to do if a file with the same name already exists.
- This is especially important in batch operations or when writing to shared directories.
- The `AbstractBaseWriter` provides several options to handle this scenario through the use of
  an `enum` called `ExistingFileMode`.

It is important to handle these options carefully in your writer's `save()` method to
avoid data loss or conflicts.
<!-- adding this here too early might be confusing
```python
from imgtools.io.writers import ExistingFileMode

writer = ExampleWriter(
    root_directory="./data",
    filename_format="{person_name}/{date}_{message_type}.txt",
    existing_file_mode=ExistingFileMode.OVERWRITE,
)

data = "Hello, World!"
writer.save(
  data, 
  person_name="JohnDoe",
  date="2025-01-01",
  message_type="greeting"
)
# Should see a log message (assuming log level is set to `DEBUG`)
# [DEBUG] File data/JohnDoe/2025-01-01_greeting.txt exists. Deleting and overwriting.
``` 
-->

::: imgtools.io.writers.ExistingFileMode
    options:
      heading_level: 4

## Advanced Concepts

### Lifecycle Management

**Context Manager Support**:

- Writers can be used with `with` statements to ensure proper setup and cleanup.  

**What Happens on Exit?**:

- Removes lock files used for the index file.  
- Deletes empty directories created during the writing process (if no files were written).  

Example:

```python
with TextWriter(root_directory="/data", filename_format="{id}.txt") as writer:
  data = "Hello, World!"
  writer.save(data, id="1234")
```

### Previewing File Paths and Caching Context

In the simplest usage of a writer, users can pass in the context information as
keyword arguments to each `save()` call.

However, this can become cumbersome when the same context variables are used across multiple
save operations.

**Example:**

In the above example, the `date` and `message_type` context variables are the same for all
students. Instead of passing them in every time, you can store these variables in the writer
itself and update them as needed.

Let's use the following example to illustrate this:

Say we want to save greetings for students in a particular highschool class:

```python
writer = TextWriter(
    root_directory="./data",
    filename_format="{grade}/{class_subject}/{person_name}/{date}_{message_type}.txt",
)
```

=== "Basic Usage"

    We see here that the context variables for `grade`,
    `class_subject`, `date`, and `message_type`
    are the same for all students.

    This can become even worse with more
    context variables, allowing for mistakes, and making the code harder to read.

    ```python
    
    student, message = "Alice", "Hello, Alice!"
    writer.save(
        message,
        person_name=student,
        grade="12",
        class_subject="math",
        date="2025-01-01",
        message_type="greeting"
    )

    student, message = "Bob", "Good morning, Bob!"
    writer.save(
        message,
        person_name=student,
        grade="12",
        class_subject="math",
        date="2025-01-01",
        message_type="greeting"
    )
    ```

=== "Setting Context Variables manually"

    Instead of passing in the context variables every time,
    you can store these variables in the writer and update them as needed
    using the `set_context()` method.

    Then only pass in the unique context variables for each `.save()` operation.

    ```python
    writer.set_context(
      grade="12",
      class_subject="math",
      date="2025-01-01",
      message_type="greeting"
    )

    student, message = "Alice", "Hello, Alice!"
    writer.save(message, person_name=student)

    student, message = "Bob", "Good morning, Bob!"
    writer.save(message, person_name=student)
    ```

=== "Setting Context Variables during Initialization"

    If majority of the context variables are the same across all save 
    operations, you can set context when initializing the writer.

    Note that here, we must pass as a dictionary to the `context` parameter 
    instead of individual keyword arguments.

    ```python
    writer = TextWriter(
        root_directory="./data",
        filename_format="{class_subject}/{person_name}/{date}_{message_type}.txt",
        context={"grade": "12", "class_subject": "math", "date": "2025-01-01", "message_type": "greeting"}
    )

    student, message = "Alice", "Hello, Alice!"
    writer.save(message, person_name=student)

    student, message = "Bob", "Good morning, Bob!"
    writer.save(message, person_name=student)
    ```

#### Previewing File Paths

Oftentimes, you may want to check if a file exists before performing an expensive computation.
If you set the existence mode to `ExistingFileMode.SKIP`, the `preview_path()` method will return `None` if the
file already exists, allowing you to skip the computation.

This method also caches the additional context variables for future use.

Here's an example of how you might handle this:

```python
# assuming writer is already initialized with `existing_file_mode=ExistingFileMode.SKIP`

# set some context variables
writer.set_context(class_subject="math", date="2025-01-01", message_type="greeting")

if (path := writer.preview_path(person_name="Alice")) is None:
    print("File already exists, skipping computation.")
else:
    print(f"Proceed with computation for {path}")
    ... 
    # perform expensive computation 
    ...
    writer.save(content="Hello, world!")
```

### Index File Management

**What is the Index File?**:

- A CSV file used to log details about saved files, like their paths and context variables.  
- Helps track what files have been written, especially useful in batch operations.
- Additionally can save all the context variables used for each file, convienient for
  saving additional metadata, while improving traceability.

**How It Works**:

- By default, it is named `{root_directory.name}_index.csv`.
- You can customize the filename or provide an absolute path for more control.  
- This is something that the `save()` method in the `AbstractBaseWriter` should **optionally**
  implement, or let users decide to include the index by calling `add_to_index(path)` after `save()`.

**Key Features**:

- **Customizable Filename**: Use `index_filename` to set a custom name or absolute path.
- **Absolute/Relative Paths**: Control file paths in the index with `absolute_paths_in_index`.
- **Inter-process Locking**: Prevents conflicts in concurrent writing environments.

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
