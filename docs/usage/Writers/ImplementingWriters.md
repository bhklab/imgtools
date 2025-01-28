# Extending the `AbstractBaseWriter` class

The `AbstractBaseWriter` is designed to be extended, allowing you to create custom
writers tailored to your specific needs. This guide will walk you through the
steps to extend the class and implement your custom functionality.

---

## Setting Up Your Writer

To create a custom writer, you need to extend the `AbstractBaseWriter` and
implement the `save` method. This method is the core of your writer, handling
how and where data is saved.

For a walkthrough of **all** key methods and features, see the
[Key Methods](#key-methods) section below.

### Steps to Set Up

1. **Inherit from `AbstractBaseWriter`**:  
   Create a new class and extend `AbstractBaseWriter` with the appropriate type.
   If you are saving text data, use `AbstractBaseWriter[str]`, for example.
   If you are saving image data, use `AbstractBaseWriter[sitk.Image]`.

2. **Define the `save` Method**:  
  Use `resolve_path()` or `preview_path()` to generate file paths.  
  Implement the logic for saving data.  

3. **Customize Behavior (Optional)**:
  Override any existing methods for specific behavior.  
  Add additional methods or properties to enhance functionality.  

### Simple Example

```python
from pathlib import Path
from imgtools.io import AbstractBaseWriter

class MyCustomWriter(AbstractBaseWriter[str]):
    def save(self, content: str, **kwargs) -> Path:
        # Resolve the output file path
        output_path = self.resolve_path(**kwargs)

        # Write content to the file
        with output_path.open(mode="w", encoding="utf-8") as f:
            f.write(content)

        # Log and track the save operation
        self.add_to_index(output_path, **self.context)

        return output_path
```

---

## Implementing the `save` Method

The `save` method is the heart of your custom writer. It determines how data
is written to files and interacts with the core features of `AbstractBaseWriter`.

### Key Responsibilities of `save`

1. **Path Resolution**:

    - Use `resolve_path()` to dynamically generate file paths based on the provided
        context and filename format.
    - You can optionally use `preview_path()` as well.
    - Ensure paths are validated to prevent overwriting or duplication.

2. **Data Writing**:  
  
    - Define how the content will be written to the resolved path.  
    - Use file-handling best practices to ensure reliability.

3. **Logging and Tracking**:  
  
    - Log each save operation for debugging or auditing purposes.  
    - Use `add_to_index()` to maintain a record of saved files and their associated
        context variables.

4. **Return Value**:  
  
    - Return the `Path` object representing the saved file.  
    - This allows users to access the file path for further processing or verification.

### Example Implementation

Here’s a minimal implementation of the `save` method for a custom writer.

```python
from pathlib import Path
from mypackage.abstract_base_writer import AbstractBaseWriter

class MyCustomWriter(AbstractBaseWriter[str]):
    def save(self, content: str, **kwargs) -> Path:
        # Step 1: Resolve the output file path
        # you can try-catch this in case set to "FAIL" mode
        # or just let the error propagate
        output_path = self.resolve_path(**kwargs) # resolve_path will always return the path

        # OPTIONAL handling for "SKIP" modes
        if output_path.exists():
            # this will only be true if the file existence mode
            # is set to SKIP
            # - OVERWRITE will have already deleted the file
            # - upto developer to choose to handle this if set to SKIP
            pass

        # Step 2: Write the content to the resolved path
        with output_path.open(mode="w", encoding="utf-8") as f:
            f.write(content)

        # Step 3: Log and track the save operation
        self.add_to_index(output_path, filepath_column="filepath", **kwargs)

        # Step 4: ALWAYS Return the saved file path
        return output_path
```

---

## Key Methods

The `AbstractBaseWriter` provides several utility methods that simplify file writing
and context management. These methods are designed to be flexible and reusable,
allowing you to focus on your custom implementation.

<!-- 
**old examples**:

For the descriptions below, lets consider this subclass of `AbstractBaseWriter`:

```python
from imgtools.io.abstract_base_writer import AbstractBaseWriter

class ReportCardWriter(AbstractBaseWriter):
    def save(self, content: str, **kwargs) -> Path:
        output_path = self.resolve_path(**kwargs)
        with output_path.open(mode="w", encoding="utf-8") as f:
            f.write(content)
        self.add_to_index(output_path)
        return output_path
```

We will demonstrate the methods using this instantiated writer:

```python
writer = ReportCardWriter(
  root_dir="./results/outputs", 
  filename_format="{subject}/{name}_report.txt",
)
```

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

-->

::: imgtools.io.writers.AbstractBaseWriter.resolve_path

::: imgtools.io.writers.AbstractBaseWriter.preview_path

::: imgtools.io.writers.AbstractBaseWriter.clear_context

---

::: imgtools.io.writers.AbstractBaseWriter.add_to_index


---

::: imgtools.io.writers.AbstractBaseWriter._generate_path

**What It Does**:

- A helper method for resolving file paths based on the current context and
  filename format.  
- Automatically sanitizes filenames if `sanitize_filenames=True`.

**When to Use It**:

- Typically called internally by `resolve_path()` and `preview_path()`, which handle
  additional validation and error handling.
- Can be called by your class methods to generate paths without the additional
  context checks.

**Example**:

```python
custom_path = writer._generate_path(subject="math", name="example")
print(f"Generated path: {custom_path}")
```

---

By using these key methods effectively, you can customize your writer to handle
a wide range of file-writing scenarios while maintaining clean and consistent
logic.
