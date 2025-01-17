# Extending the `AbstractBaseWriter` class

The `AbstractBaseWriter` is designed to be extended, allowing you to create custom
writers tailored to your specific needs. This guide will walk you through the
steps to extend the class and implement your custom functionality.

---

## 3. Setting Up Your Writer

To create a custom writer, you need to extend the `AbstractBaseWriter` and
implement the `save` method. This method is the core of your writer, handling
how and where data is saved.

### Steps to Set Up

1. **Inherit from `AbstractBaseWriter`**:  
   Create a new class and extend `AbstractBaseWriter`.

2. **Define the `save` Method**:  
   - Implement the logic for saving data.  
   - Use `resolve_path()` or `preview_path()` to generate file paths.  

3. **Customize Behavior (Optional)**:  
   - Override any existing methods for specific behavior.  
   - Add additional methods or properties to enhance functionality.  

### Example

```python
from pathlib import Path
from mypackage.abstract_base_writer import AbstractBaseWriter

class MyCustomWriter(AbstractBaseWriter):
    def save(self, content: str, **kwargs) -> Path:
        # Resolve the output file path
        output_path = self.resolve_path(**kwargs)

        # Write content to the file
        with output_path.open(mode="w", encoding="utf-8") as f:
            f.write(content)

        # Log and track the save operation
        self.dump_to_csv(output_path, **self.context)

        return output_path
```

---

## 4. Implementing the `save` Method

The `save` method is the heart of your custom writer. It determines how data
is written to files and interacts with the core features of `AbstractBaseWriter`.

### Key Responsibilities of `save`

1. **Path Resolution**:

    - Use `resolve_path()` to dynamically generate file paths based on the provided
        context and filename format.  
    - Ensure paths are validated to prevent overwriting or duplication.

2. **Data Writing**:  
  
    - Define how the content will be written to the resolved path.  
    - Use file-handling best practices to ensure reliability.

3. **Logging and Tracking**:  
  
    - Log each save operation for debugging or auditing purposes.  
    - Use `dump_to_csv()` to maintain a record of saved files and their associated
        context variables.

4. **Return Value**:  
  
    - Return the `Path` object representing the saved file.  
    - This allows users to access the file path for further processing or verification.

### Example Implementation

Here’s a minimal implementation of the `save` method for a custom writer:

```python
from pathlib import Path
from mypackage.abstract_base_writer import AbstractBaseWriter

class MyCustomWriter(AbstractBaseWriter):
    def save(self, content: str, **kwargs) -> Path:
        # Step 1: Resolve the output file path
        try:
            output_path = self.resolve_path(**kwargs)
        except FileExistsError:
            # Handle "FAIL" mode: File already exists
            # Optionally, log or re-raise the error based on your needs
            raise

        # Optional handling for "RAISE_WARNING" mode
        if output_path.exists():
            # this will only be true if the file existence mode
            # is set to RAISE_WARNING
            # as OVERWRITE will have already deleted the file
            # optionally choose to handle this if you want to
            pass

        # Step 2: Write the content to the resolved path
        with output_path.open(mode="w", encoding="utf-8") as f:
            f.write(content)

        # Step 3: Log and track the save operation
        self.dump_to_csv(output_path, **self.context)

        # Step 4: Return the saved file path
        return output_path

```

## 5. Key Methods

The `AbstractBaseWriter` provides several utility methods that simplify file writing
and context management. These methods are designed to be flexible and reusable,
allowing you to focus on your custom implementation.

For the descriptions below, lets consider this subclass of `AbstractBaseWriter`:

```python
from mypackage.abstract_base_writer import AbstractBaseWriter

class ReportCardWriter(AbstractBaseWriter):
    def save(self, content: str, **kwargs) -> Path:
        output_path = self.resolve_path(**kwargs)
        with output_path.open(mode="w", encoding="utf-8") as f:
            f.write(content)
        self.dump_to_csv(output_path, **self.context)
        return output_path
```

We will demonstrate the methods using this instantiated writer:

```python
writer = ReportCardWriter(
  root_dir="./results/outputs", 
  filename_format="{subject}/{name}_report.txt",
)
```

---

### `resolve_path`

**What It Does**:

- Dynamically generates a file path based on the provided context and filename format.

**When to Use It**:

- This method is meant to be used in the `save` method to determine the file’s
  target location.
- It ensures you’re working with a valid path and can handle file existence scenarios.

**Example**:

```python
output_path = writer.resolve_path(subject="math", name="example")
print(f"Resolved path: {output_path}")
```

---

### `preview_path`

**What It Does**:

- Pre-checks the file path based on context without writing the file.  
- Returns `None` if the file exists and the mode is set to `SKIP`.  
- Raises a `FileExistsError` if the mode is set to `FAIL`.
- An added benefit of using `preview_path` is that it automatically caches the context
  variables for future use, and `save()` can be called without passing in the context
  variables again.

**When to Use It**:

- Use this method to skip expensive computations if a file already exists and you
  don’t want to overwrite it.  

**Example**:

```python
if writer.preview_path(subject="math", name="JohnDoe") is None:
    print("File already exists, skipping computation.")
else:
    print("Proceed with computation.")

...
# no need to pass in the context variables again
output_path = writer.save(content="Hello, world!")
print(output_path)
# 'results/outputs/math/JohnDoe_report.txt'
```

---

### `dump_to_csv`

**What It Does**:

- Logs the file’s path and associated context variables to a shared CSV index file.  
- Uses inter-process locking to avoid conflicts when multiple writers are active.

**When to Use It**:

- Use this method to maintain a centralized record of saved files for auditing
  or debugging.  

**NOTE**: if the index file already exists upon class instantiation, it will be
DELETED. This is to ensure that the index file is always up-to-date with the
current state of the writer.

---

### `set_context`

**What It Does**:

- Updates the writer’s internal context with new key-value pairs.  
- Allows for dynamic updates to context variables across multiple saves.

**When to Use It**:

- Use this method to predefine context values that will remain consistent across
  multiple save operations.  

**Example**:

Imagine that for this writer session, we have a fixed subject of "math", but
many names of students to save reports for. We can set the subject once and then
update the name for each student:

```python
writer.set_context(subject="math")
out_path = writer.save(content="Hello, world!", name="student1")
print(out_path)
# 'results/outputs/math/student1_report.txt'
output_path = writer.save(content="Hello, world!", name="student2")
print(output_path)
# 'results/outputs/math/student2_report.txt'
```

---

### `_generate_path`

**What It Does**:

- A helper method for resolving file paths based on the current context and
  filename format.  
- Automatically sanitizes filenames if `sanitize_filenames=True`.

**When to Use It**:

- Typically called internally by `resolve_path()` but can be useful for debugging
  or custom path generation.

**Example**:

```python
custom_path = writer._generate_path(subject="math", name="example")
print(f"Generated path: {custom_path}")
```

---

By using these key methods effectively, you can customize your writer to handle
a wide range of file-writing scenarios while maintaining clean and consistent
logic.
