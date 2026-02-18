#!/usr/bin/env python3
"""
Simple GUI to run all utils folder scripts
==========================================

A tkinter-based GUI that allows running all scripts in the utils folder
with output display and error handling.
"""

import json
import queue
import select
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk, simpledialog
from typing import Dict, List, Optional


class UtilsRunnerGUI:
    """Simple GUI for running utils scripts.

    Provides a tkinter-based interface to run utility scripts from the utils folder
    with real-time output display, error handling, and process management.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("APGI Utils Scripts Runner")
        self.root.geometry("800x600")

        # Get utils directory
        self.utils_dir = Path(__file__).parent / "app" / "utils"

        # Validate utils directory exists
        if not self.utils_dir.exists():
            print(f"Warning: Utils directory not found at {self.utils_dir}")
            self.utils_dir = None

        # Output queue for thread-safe updates
        self.output_queue = queue.Queue()

        # Maximum lines to keep in output to prevent performance issues
        self.max_output_lines = 2000

        # Output tag constants
        self.TAG_INFO = "info"
        self.TAG_ERROR = "error"
        self.TAG_SUCCESS = "success"
        self.TAG_WARNING = "warning"

        # Load configuration
        self.config = self.load_config()

        self.scripts = self.get_script_list()

        # Store running processes
        self.running_processes: Dict[str, subprocess.Popen] = {}

        self.setup_ui()

        # Add keyboard shortcut for quitting (Ctrl+Q or Cmd+Q)
        self.root.bind("<Control-q>", lambda e: self.quit_application())
        self.root.bind("<Command-q>", lambda e: self.quit_application())

        # Handle window close button
        self.root.protocol("WM_DELETE_WINDOW", self.quit_application)

    def load_config(self) -> Dict:
        """Load configuration from JSON file.

        Returns:
            Configuration dictionary with default values if file not found.
        """
        config_path = self.utils_dir / "utils_script_config.json" if self.utils_dir else None
        default_config = {
            "script_categories": {
                "utilities": {
                    "description": "General utility scripts",
                    "scripts": [],
                    "timeout": 3600,
                }
            },
            "default_settings": {
                "timeout": 3600,
                "max_retries": 2,
                "retry_delay": 1,
                "enable_execution_time": True,
                "log_level": "INFO",
            },
        }

        try:
            if config_path.exists():
                with open(config_path, "r") as f:
                    return json.load(f)
            else:
                # Create default config file
                with open(config_path, "w") as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            self.log_output(f"Warning: Could not load config: {e}", self.TAG_WARNING)
            return default_config

    def get_script_timeout(self, script_name: str) -> int:
        """Get timeout for a specific script from configuration.

        Args:
            script_name: Name of the script.

        Returns:
            Timeout in seconds.
        """
        for category in self.config.get("script_categories", {}).values():
            if script_name in category.get("scripts", []):
                return category.get("timeout", self.config["default_settings"]["timeout"])
        return self.config["default_settings"]["timeout"]

    def prompt_for_arguments(self, script_name: str) -> List[str]:
        """Prompt user for script arguments.

        Args:
            script_name: Name of the script.

        Returns:
            List of arguments to pass to the script.
        """
        dialog = simpledialog.askstring(
            "Script Arguments",
            f"Enter arguments for {script_name} (optional):",
            parent=self.root,
        )

        if dialog:
            # Split arguments while respecting quotes
            import shlex

            try:
                return shlex.split(dialog)
            except ValueError:
                # Fallback to simple split if shlex fails
                return dialog.split()
        return []

    def get_script_list(self) -> List[Path]:
        """Get all Python scripts in utils directory.

        Returns:
            List of Path objects for executable Python scripts.
        """
        scripts = []
        if self.utils_dir and self.utils_dir.exists() and self.utils_dir.is_dir():
            for file_path in self.utils_dir.glob("*.py"):
                if file_path.name != "__init__.py" and self._is_executable_script(file_path):
                    scripts.append(file_path)
        return sorted(scripts)

    def _is_executable_script(self, script_path: Path) -> bool:
        """Check if a script is executable.

        Args:
            script_path: Path to the script file.

        Returns:
            True if script appears to be executable, False otherwise.
        """
        try:
            # Check if file has shebang or is a valid Python file
            with open(script_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                # Check for shebang or just ensure it's a Python file
                return first_line.startswith("#!") or script_path.suffix == ".py"
        except (UnicodeDecodeError, IOError):
            return False

    def setup_ui(self):
        """Setup the user interface.

        Creates the main layout with script list, control buttons,
        status display, and output area.
        """
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

        # Title
        title_label = ttk.Label(
            main_frame, text="APGI Utils Scripts Runner", font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # Scripts list frame
        list_frame = ttk.LabelFrame(main_frame, text="Available Scripts", padding="5")
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))

        # Scripts listbox with scrollbar
        list_scrollbar = ttk.Scrollbar(list_frame)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.scripts_listbox = tk.Listbox(
            list_frame, yscrollcommand=list_scrollbar.set, height=15, width=40
        )
        self.scripts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scrollbar.config(command=self.scripts_listbox.yview)

        # Populate scripts list
        for script in self.scripts:
            self.scripts_listbox.insert(tk.END, script.name)

        # Control buttons frame
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N), padx=(0, 10))

        # Buttons
        self.run_button = ttk.Button(
            control_frame, text="Run Selected", command=self.run_selected_script
        )
        self.run_button.pack(pady=5, fill=tk.X)

        self.run_args_button = ttk.Button(
            control_frame,
            text="Run with Arguments",
            command=self.run_selected_script_with_args,
        )
        self.run_args_button.pack(pady=5, fill=tk.X)

        self.run_all_button = ttk.Button(
            control_frame, text="Run All Scripts", command=self.run_all_scripts
        )
        self.run_all_button.pack(pady=5, fill=tk.X)

        self.stop_button = ttk.Button(
            control_frame,
            text="Stop Selected",
            command=self.stop_selected_script,
            state=tk.DISABLED,
        )
        self.stop_button.pack(pady=5, fill=tk.X)

        self.clear_button = ttk.Button(
            control_frame, text="Clear Output", command=self.clear_output
        )
        self.clear_button.pack(pady=5, fill=tk.X)

        self.quit_button = ttk.Button(control_frame, text="Quit", command=self.quit_application)
        self.quit_button.pack(pady=5, fill=tk.X)

        # Status frame
        status_frame = ttk.LabelFrame(control_frame, text="Status", padding="5")
        status_frame.pack(pady=20, fill=tk.X)

        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack()

        # Progress bar
        self.progress = ttk.Progressbar(control_frame, mode="indeterminate", length=200)
        self.progress.pack(pady=10, fill=tk.X)

        # Output frame
        output_frame = ttk.LabelFrame(main_frame, text="Output", padding="5")
        output_frame.grid(
            row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0)
        )

        # Output text area
        self.output_text = scrolledtext.ScrolledText(
            output_frame, height=15, wrap=tk.WORD, font=("Courier", 9)
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for different output types
        self.output_text.tag_config(self.TAG_INFO, foreground="black")
        self.output_text.tag_config(self.TAG_ERROR, foreground="red")
        self.output_text.tag_config(self.TAG_SUCCESS, foreground="green")
        self.output_text.tag_config(self.TAG_WARNING, foreground="orange")

        # Start processing output queue
        self.process_output_queue()

    def log_output(self, message: str, tag: str = None):
        """Add message to output queue for thread-safe logging.

        Args:
            message: The message to log.
            tag: The color tag to apply (info, error, success, warning).
        """
        if tag is None:
            tag = self.TAG_INFO
        self.output_queue.put((message, tag))

    def _log_output(self, message: str, tag: str):
        """Thread-safe output logging."""
        self.output_text.insert(tk.END, message + "\n", tag)
        self.output_text.see(tk.END)

        # Limit output lines to prevent performance issues
        line_count = int(self.output_text.index("end-1c").split(".")[0])
        if line_count > self.max_output_lines:
            # Keep only the last max_output_lines lines
            self.output_text.delete(1.0, f"{line_count - self.max_output_lines + 1}.0")

    def process_output_queue(self):
        """Process queued output messages in the main thread."""
        try:
            while True:
                message, tag = self.output_queue.get_nowait()
                self._log_output(message, tag)
        except queue.Empty:
            pass
        self.root.after(100, self.process_output_queue)

    def update_status(self, message: str):
        """Update status label.

        Args:
            message: The status message to display.
        """
        self.root.after_idle(lambda: self._safe_update_status(message))

    def _safe_update_status(self, message: str):
        """Thread-safe status update."""
        self.status_label.config(text=message)

    def get_selected_script(self) -> Optional[Path]:
        """Get the currently selected script.

        Returns:
            Path to selected script or None if no selection.
        """
        selection = self.scripts_listbox.curselection()
        if selection:
            index = selection[0]
            return self.scripts[index]
        return None

    def run_script(
        self,
        script_path: Path,
        args: List[str] = None,
        wait: bool = False,
        timeout: int = None,
    ):
        """Run a script with optional waiting and timeout.

        Args:
            script_path: Path to the script to run.
            args: List of arguments to pass to the script.
            wait: If True, wait for completion and return success status.
            timeout: Timeout in seconds, uses config default if None.

        Returns:
            True if script started (wait=False) or completed successfully (wait=True).
        """
        if args is None:
            args = []
        script_name = script_path.name
        self.log_output(f"Running script: {script_name}", self.TAG_INFO)
        return self._run_script_thread(script_path, args, timeout=timeout, wait=wait)

    def run_selected_script(self):
        """Run the selected script in a separate thread."""
        script = self.get_selected_script()
        if not script:
            self.log_output("No script selected", self.TAG_ERROR)
            return

        self.run_script(script)

    def run_selected_script_with_args(self):
        """Run the selected script with custom arguments."""
        script = self.get_selected_script()
        if not script:
            self.log_output("No script selected", self.TAG_ERROR)
            return

        args = self.prompt_for_arguments(script.name)
        self.run_script(script, args=args)

    def run_all_scripts(self):
        """Run all scripts sequentially."""
        if not self.scripts:
            self.log_output("No scripts found", self.TAG_ERROR)
            return

        def run_all():
            for i, script in enumerate(self.scripts):
                self.log_output(
                    f"Running script {i + 1}/{len(self.scripts)}: {script.name}",
                    self.TAG_INFO,
                )
                self.scripts_listbox.selection_clear(0, tk.END)
                self.scripts_listbox.selection_set(i)
                self.scripts_listbox.see(i)

                success = self.run_script(
                    script, wait=True, timeout=self.get_script_timeout(script.name)
                )
                if not success:
                    self.log_output(
                        f"Script {script.name} failed, stopping execution",
                        self.TAG_ERROR,
                    )
                    break

            self.log_output("All scripts execution completed", self.TAG_SUCCESS)
            self.update_status("Ready")
            self.progress.stop()

        # Run in separate thread to avoid blocking GUI
        thread = threading.Thread(target=run_all, daemon=True)
        thread.start()

    def run_script(
        self,
        script: Path,
        wait: bool = False,
        retry_count: int = 0,
        timeout: int = None,
        args: List[str] = None,
    ) -> bool:
        """Run a single script.

        Args:
            script: Path to the script to run.
            wait: If True, block until script completes and return success status.
                 If False, run asynchronously and return True immediately.
            retry_count: Current retry attempt (for internal use).
            timeout: Maximum execution time in seconds (uses config if None).
            args: Additional arguments to pass to the script.

        Returns:
            True if script started successfully, False if error occurred.
            When wait=True, returns True if script completed with return code 0.
        """
        import time

        start_time = time.time()
        script_name = script.name

        # Prepare command
        cmd = [sys.executable, str(script)]

        # Add auto flag for scripts that support it to prevent hanging
        auto_scripts = {"quick_deploy.py", "setup.py"}
        if script_name in auto_scripts:
            cmd.append("--auto")

        # Add user-provided arguments
        if args:
            cmd.extend(args)

        # Use configuration timeout if not specified
        if timeout is None:
            timeout = self.get_script_timeout(script.name)

        # Start process
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=self.utils_dir.parent,
            )

            self.running_processes[script_name] = process

            # Read output in real-time
            def read_output():
                script_timeout = self.get_script_timeout(script_name)
                start_time = time.time()

                while True:
                    # Wait for output with a short timeout to allow timeout checking
                    ready, _, _ = select.select([process.stdout], [], [], 1.0)
                    if ready:
                        output = process.stdout.readline()
                        if not output and process.poll() is not None:
                            break
                        if output:
                            self.log_output(output.strip(), self.TAG_INFO)
                            # Reset timeout on output to allow slow processes full time
                            start_time = time.time()

                    # Check timeout even without output
                    if time.time() - start_time > script_timeout:
                        self.log_output(
                            f"Script timeout after {script_timeout} seconds",
                            self.TAG_ERROR,
                        )
                        process.terminate()
                        break

                # Get final return code
                return_code = process.poll()
                if return_code == 0:
                    self.log_output(
                        f"✅ {script_name} completed successfully in {time.time() - start_time:.2f}s",
                        self.TAG_SUCCESS,
                    )
                else:
                    self.log_output(
                        f"❌ {script_name} failed with return code {return_code}",
                        self.TAG_ERROR,
                    )

                # Remove from running processes
                if script_name in self.running_processes:
                    del self.running_processes[script_name]

                # Re-enable run button if no processes running
                if not self.running_processes:
                    self.root.after(0, self._update_button_states)

            # Start output reading thread
            output_thread = threading.Thread(target=read_output, daemon=True)
            output_thread.start()

            # Update button states
            self._update_button_states()

            if wait:
                output_thread.join()
                return process.returncode == 0
            else:
                return True

        except Exception as e:
            self.log_output(f"Error running {script.name}: {str(e)}", self.TAG_ERROR)
            self.progress.stop()
            self.update_status("Error")
            # Disable stop button on error
            self.root.after_idle(self._update_stop_button_state)

            # Retry logic for exceptions
            if retry_count < 2:
                self.log_output(
                    f"Retrying {script.name} due to exception (attempt {retry_count + 1}/2)",
                    self.TAG_WARNING,
                )
                time.sleep(1)
                return self.run_script(script, wait, retry_count + 1, timeout)
            return False

    def _force_kill_process(self, process: subprocess.Popen, script_name: str):
        """Force kill a stubborn process.

        Args:
            process: The subprocess to kill.
            script_name: Name of the script for logging.
        """
        try:
            if process.poll() is None:  # Process is still running
                process.terminate()  # Try graceful termination first
                try:
                    process.wait(timeout=5)  # Wait up to 5 seconds
                except subprocess.TimeoutExpired:
                    process.kill()  # Force kill if termination fails
                    self.log_output(f"Force killed {script_name}", self.TAG_WARNING)
        except Exception as e:
            self.log_output(f"Error killing process {script_name}: {e}", self.TAG_ERROR)

    def _update_button_states(self):
        """Update button states based on running processes."""
        if self.running_processes:
            self.run_button.config(state=tk.DISABLED)
            self.run_args_button.config(state=tk.DISABLED)
            self.run_all_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
        else:
            self.run_button.config(state=tk.NORMAL)
            self.run_args_button.config(state=tk.NORMAL)
            self.run_all_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def _update_stop_button_state(self):
        """Update stop button state based on running processes."""
        if self.running_processes:
            self.stop_button.config(state=tk.NORMAL)
        else:
            self.stop_button.config(state=tk.DISABLED)

    def stop_selected_script(self):
        """Stop the selected script if it's running."""
        script = self.get_selected_script()
        if not script:
            self.log_output("No script selected", self.TAG_ERROR)
            return

        if script.name in self.running_processes:
            try:
                process = self.running_processes[script.name]
                self._force_kill_process(process, script.name)
                self.log_output(f"Stopped: {script.name}", self.TAG_WARNING)
                del self.running_processes[script.name]
                # Disable stop button if no processes are running
                self._update_stop_button_state()
                self.progress.stop()
                self.update_status("Ready")
            except Exception as e:
                self.log_output(f"Error stopping {script.name}: {str(e)}", self.TAG_ERROR)
        else:
            self.log_output(f"Script {script.name} is not running", self.TAG_WARNING)

    def clear_output(self):
        """Clear the output text area."""
        self.output_text.delete(1.0, tk.END)
        self.log_output("Output cleared", self.TAG_INFO)

    def quit_application(self):
        """Quit the application safely.

        Stops all running processes and closes the application.
        """
        # Stop all running processes
        for script_name, process in list(self.running_processes.items()):
            try:
                if process.poll() is None:  # Process is still running
                    self._force_kill_process(process, script_name)
                    self.log_output(f"Terminated process: {script_name}", self.TAG_WARNING)
            except Exception as e:
                self.log_output(f"Error terminating process {script_name}: {e}", self.TAG_ERROR)

        # Clear running processes
        self.running_processes.clear()

        # Log quit message
        self.log_output("Quitting application...", self.TAG_INFO)

        # Wait a moment for messages to be processed
        self.root.update_idletasks()

        # Quit the application
        self.root.quit()
        self.root.destroy()


def main():
    """Launch the utils runner GUI."""
    try:
        # Create and run the GUI
        root = tk.Tk()
        app = UtilsRunnerGUI(root)

        # Center window on screen
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")

        root.mainloop()

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("This script requires tkinter, which should come with Python.")
        sys.exit(1)
    except tk.TclError as e:
        print(f"❌ Tkinter Error: {e}")
        print("There was an error initializing the GUI.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
