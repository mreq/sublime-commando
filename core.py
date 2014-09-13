#
# Core library of helper functions to simplify calling command-line commands
# for the current file or path.
#
import sublime, sublime_plugin
import Default.exec as ex
import subprocess
import threading
import time
import os

def plugin_loaded():
  pass

class CommandThread(threading.Thread):
  def __init__(self, command, callback = None, working_dir = None, env = None):
    super().__init__()
    self.command = command
    self.callback = callback
    self.working_dir = working_dir
    self.env = env

  def run(self):
    error = False
    try:
      if self.working_dir is not None:
        os.chdir(self.working_dir)
        full_env = os.environ.copy()
        if isinstance(self.env, dict):
          full_env.update(self.env)
        output = subprocess.check_output(self.command, env=full_env, stderr=subprocess.STDOUT).decode("utf-8")
      else:
        output = "Working directory not found!"
        error = True
    except subprocess.CalledProcessError as e:
      output = '$ ' + ' '.join(e.cmd) + '\n' + e.output.decode('utf-8')
      error = True
    # except:
    #   output = "Other Error!"

    if self.callback is not None:
      self.callback(output, error)

class Command:
  def get_working_dir(self):
    return os.getcwd()

  def get_file_dir(self):
    view = self.get_view()
    if view is not None:
      if view.file_name() is not None:
        return os.path.dirname(view.file_name())
    return None

  def exec_command(self, command, params = None, callback = None, env = None):
    self.command = command
    self.params = params if params is not None else []
    self.full_command = [self.command]+self.params
    self.callback = callback if callback is not None else self.panel
    self.env = env if env is not None else {}

    self.loop = 0
    self.long_command = False

    self.thread = CommandThread(self.full_command, self.on_output, self.get_working_dir(), self.env)
    self.thread.start()
    sublime.set_timeout(self.watch_thread, 500)

  def watch_thread(self):
    self.loop = (self.loop+1) % 4
    if self.thread.is_alive():
      self.long_command = True
      self.status('commando-command', ' '.join(self.full_command)+': Running'+'.'*self.loop+' '*(3-self.loop))
      sublime.set_timeout(lambda: self.watch_thread(),200)
    elif self.long_command:
      self.status('commando-command', ' '.join(self.full_command)+': Done!')
      sublime.set_timeout(lambda:self.status('commando-command',''),3000)

  def get_window(self):
    try:
      return self.window
    except AttributeError:
      return self.view.window()

  def get_view(self):
    try:
      return self.view
    except AttributeError:
      return self.window.active_view()

  def on_output(self, output, error = None):
    if error:
      self.panel('Error\n-----\n'+output)
    elif self.callback is not None:
      self.callback(output)

  def panel(self, contents):
    if contents.rstrip() != '':
      p = self.get_window().create_output_panel("command")
      p.run_command("simple_insert", {"contents": contents})
      self.get_window().run_command("show_panel",{"panel":"output.command"})

  def select(self, *args, **kwargs):
    # allows us to chain quick panels (otherwise "Quick panel unavailable" error is thrown)
    sublime.set_timeout(lambda: self.get_window().show_quick_panel(*args, **kwargs), 10)

  def prompt(self, caption, initial_text = "", on_done = None, on_change = None, on_cancel = None):
    self.get_window().show_input_panel(caption, initial_text, on_done, on_change, on_cancel)

  def status(self, name, contents):
    self.get_view().set_status(name, contents)

  def scratch(self, contents, name = None, syntax = None, ro = False):
    new_view = self.get_window().new_file()
    new_view.set_scratch(True)
    if name is not None:
      new_view.set_name(name)
    if syntax is not None:
      new_view.set_syntax_file("Packages/"+syntax+"/"+syntax+".tmLanguage")
    new_view.run_command("simple_insert", {"contents": contents})
    if ro:
      new_view.set_read_only(True)
    return new_view

  def open_file(self, filename):
    full_path = os.path.join(self.get_working_dir(), filename)
    new_view = self.get_window().open_file(full_path)
    # for some reason files are getting focus after they are opened through this
    # method.  so force focus after loading.
    if new_view is not None:
      sublime.set_timeout(lambda: self.focus_view(new_view), 100)
    return new_view

  def focus_view(self, view):
    if view.is_loading():
      sublime.set_timeout(lambda: self.focus_view(view), 100)
    else:
      self.window.focus_view(view)
      # stolen from http://www.sublimetext.com/forum/viewtopic.php?f=5&t=10997&p=48890&hilit=fuzzyfilenav#p48890
      self.window.run_command("show_panel", {"panel": "console"})
      self.window.run_command("hide_panel", {"cancel": True})

#stolen from http://www.sublimetext.com/forum/viewtopic.php?f=5&p=45149
class SimpleInsertCommand(sublime_plugin.TextCommand):
  def run(self, edit, contents):
    self.view.insert(edit, 0, contents)
    self.view.run_command("goto_line", {"line":1})

class ReplaceAllCommand(sublime_plugin.TextCommand):
  def run(self, edit, contents):
    self.view.replace(edit, sublime.Region(0,self.view.size()), contents)
    self.view.sel().clear()
    # self.view.run_command("goto_line", {"line":1})
    
