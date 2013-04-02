import sublime
import sublime_plugin
import thread
import subprocess
import os
import stat
import functools
import re

sublime_lre_controller = None

class LreController(object):
    def __init__(self):
        self.proc = None
        self.running = False
        self.auto_show_enabled = True
        self.clear_when_find_this_text = None

    def set_listener(self, listener):
        self.listener = listener
        self.output_view = self.listener.window.get_output_panel('lre')
        self.enable_word_wrap()
        self.set_color_scheme()
        self.load_config()
        return self

    def open_folder_paths(self):
        return self.listener.window.folders()

    def find_project_root_path(self):
        project_root_path = None
        for path in self.open_folder_paths():
            print "Checking ... " + path
            if (True):
                project_root_path = path
                break
        return project_root_path

    def set_permissions(self, path):
        os.chmod(path, stat.S_IRWXU | stat.S_IXGRP | stat.S_IRGRP | stat.S_IXOTH | stat.S_IROTH)

    def start_lre(self):
        project_root_path = self.find_project_root_path()
        if (project_root_path == None):
            sublime.error_message("Failed to find LRE in any of the open folders.")
        else:
            package_path = sublime.packages_path()
            self.set_permissions(package_path + "/lre/lre_wrapper")
            self.set_permissions(package_path + "/lre/run_lre.sh")
            cmd_array = [package_path + "/lre/lre_wrapper", package_path + "/lre/run_lre.sh", project_root_path]
            self.proc = subprocess.Popen(cmd_array, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.running = True
            self.show_lre_view_and_enable_autoshow()
            if self.proc.stdout:
                thread.start_new_thread(self.read_stdout, ())
            if self.proc.stderr:
                thread.start_new_thread(self.read_stderr, ())

    def enable_word_wrap(self):
        self.output_view.settings().set("word_wrap", True)

    def set_color_scheme(self):
        return

    def enable_auto_show(self):
        self.auto_show_enabled = True

    def disable_auto_show(self):
        self.auto_show_enabled = False

    def read_stdout(self):
        while True:
            data = os.read(self.proc.stdout.fileno(), 2 ** 15)
            if data != "":
                sublime.set_timeout(functools.partial(self.append_data, data), 0)
            else:
                self.proc.stdout.close()
                self.running = False
                break

    def read_stderr(self):
        while True:
            data = os.read(self.proc.stderr.fileno(), 2 ** 15)
            if data != "":
                sublime.set_timeout(functools.partial(self.append_data, data), 0)
            else:
                self.proc.stderr.close()
                self.running = False
                break

    def append_data(self, data):
        if (self.auto_show_enabled):
            self.show_lre_view()
        clean_data = data.decode("utf-8")
        clean_data = self.normalize_line_endings(clean_data)
        clean_data = self.remove_terminal_color_codes(clean_data)

        # actually append the data
        self.output_view.set_read_only(False)
        edit = self.output_view.begin_edit()

        # clear the output window when a predefined text is found.
        if (self.clear_when_find_this_text and self.clear_when_find_this_text.search(clean_data)):
            self.output_view.erase(edit, sublime.Region(0, self.output_view.size()))

        self.output_view.insert(edit, self.output_view.size(), clean_data)

        # scroll to the end of the new insert
        self.scroll_to_end_of_lre_view()

        self.output_view.end_edit(edit)
        self.output_view.set_read_only(True)

    def normalize_line_endings(self, data):
        return data.replace('\r\n', '\n').replace('\r', '\n')

    def remove_terminal_color_codes(self, data):
        color_regex = re.compile("\\033\[[0-9;m]*", re.UNICODE)
        return color_regex.sub("", data)

    def scroll_to_end_of_lre_view(self):
        (cur_row, _) = self.output_view.rowcol(self.output_view.size())
        self.output_view.show(self.output_view.text_point(cur_row, 0))

    def show_lre_view_and_enable_autoshow(self):
        self.enable_auto_show()
        self.show_lre_view()

    def show_lre_view(self):
        self.listener.window.run_command('show_panel', {'panel': 'output.lre'})

    def hide_lre_view(self):
        self.disable_auto_show()
        self.listener.window.run_command('hide_panel', {'panel': 'output.lre'})

    def stop_lre(self):
        self.proc.stdin.write('exit\n')
        self.proc.stdin.flush()
        self.running = False

    def is_lre_running(self):
        return self.running

    def reload_lre(self):
        self.proc.stdin.write('r\n')
        self.proc.stdin.flush()

    def run_all_tests(self):
        self.proc.stdin.write('\n')
        self.proc.stdin.flush()

    def output_help(self):
        self.proc.stdin.write('h\n')
        self.proc.stdin.flush()

    def toggle_notifications(self):
        self.proc.stdin.write('n\n')
        self.proc.stdin.flush()

    def pause(self):
        self.proc.stdin.write('p\n')
        self.proc.stdin.flush()

    def load_config(self):
        return
        s = sublime.load_settings("Lre.sublime-settings")
        clear_text = s.get("clear_when_find_this_text")
        if (clear_text):
           self.clear_when_find_this_text = re.compile(clear_text)
        else:
           self.clear_when_find_this_text = None

    def hide_lre_view(self):
        self.disable_auto_show()
        self.listener.window.run_command('hide_panel', {'panel': 'output.lre'})

def LreControllerSingleton():
    global sublime_lre_controller
    if sublime_lre_controller == None:
        sublime_lre_controller = LreController()
        return sublime_lre_controller
    else:
        return sublime_lre_controller

class StopLreCommand(sublime_plugin.WindowCommand):
    def run(self):
        LreControllerSingleton().set_listener(self).stop_lre()

    def is_enabled(self):
        return LreControllerSingleton().is_lre_running()

class StartLreCommand(sublime_plugin.WindowCommand):
    def run(self):
        LreControllerSingleton().set_listener(self).start_lre()

    def is_enabled(self):
        return not LreControllerSingleton().is_lre_running()

class ToggleLreCommand(sublime_plugin.WindowCommand):
    def run(self):
        if LreControllerSingleton().is_lre_running():
            LreControllerSingleton().set_listener(self).stop_lre()
            LreControllerSingleton().set_listener(self).hide_lre_view()
        else:
            LreControllerSingleton().set_listener(self).start_lre()

    def is_enabled(self):
        return True
