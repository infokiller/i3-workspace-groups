# i3 Workspace Groups

A Python library and set of command line tools for managing i3wm workspaces in
groups. I find this tool useful for managing many workspaces in i3.

[![PyPI version](https://badge.fury.io/py/i3-workspace-groups.svg)](https://badge.fury.io/py/i3-workspace-groups)
[![pipeline status](https://gitlab.com/infokiller/i3-workspace-groups/badges/master/pipeline.svg)](https://gitlab.com/infokiller/i3-workspace-groups/commits/master)

![Demo flow](./assets/demo.gif?raw=true)

## Table of Contents

- [Background](#background)
- [Installation](#installation)
- [Configuration](#configuration)
  - [i3](#i3)
  - [i3-workspace-groups](#i3-workspace-groups)
- [Usage](#usage)
  - [Example walk through](#example-walk-through)
- [Concepts](#concepts)
  - [Active workspace](#active-workspace)
  - [Active group](#active-group)
  - [Focused group](#focused-group)
  - [Default group](#default-group)
- [Limitations](#limitations)
  - [Sway compatibility](#sway-compatibility)
  - [Polybar](#polybar)

## Background

I often find myself working with many i3 workspaces at once (7-8+), usually
related to multiple projects/contexts (personal/work etc). This has caused me a
few issues, for example:

- Working with a set of workspaces of a given project/context, without being
  distracted by unrelated workspaces.
- Reusing the same workspace number in multiple projects/contexts. For example,
  I have two different emails for personal and work stuff, and I want `Super+1`
  to always switch to the workspace with the email client relevant to my current
  context.
- Finding a free workspace for a new window (that can also be reached with my
  keybindings)

This has led me to create the
[i3-workspace-groups](https://github.com/infokiller/i3-workspace-groups)
project, which enables you to define and manage groups of workspaces, each with
their own "namespace", and switch between them.

## Installation

The scripts can be installed using pip:

```shell
pipx install i3-workspace-groups
```

Then you should be able to run the command line tool
[`i3-workspace-groups`](bin/i3-workspace-groups). There are also a few utility
scripts provided that require [rofi](https://github.com/DaveDavenport/rofi) and
which are useful for interactively managing the groups, using rofi as the UI.
They include:

- [`i3-assign-workspace-to-group`](bin/i3-assign-workspace-to-group)
- [`i3-focus-on-workspace`](bin/i3-focus-on-workspace)
- [`i3-move-to-workspace`](bin/i3-move-to-workspace)
- [`i3-rename-workspace`](bin/i3-rename-workspace)
- [`i3-switch-active-workspace-group`](bin/i3-switch-active-workspace-group)

If you want to use client/server mode for improved speed/latency, it's
recommended to install one of the following tools to further improve speed:

- [socat](http://www.dest-unreach.org/socat/): available in all major distros
- BSD netcat (GNU version not supported)
- [ncat](https://nmap.org/ncat/)

## Configuration

### i3

In order to use these tools effectively, commands need to be bound to
keybindings. For example, my i3 config contains the following excerpt:

<!-- markdownlint-disable fenced-code-language -->

```ini
set $mod Mod4

set $exec_i3_groups exec --no-startup-id i3-workspace-groups

# Switch active workspace group
bindsym $mod+g exec --no-startup-id i3-switch-active-workspace-group

# Assign workspace to a group
bindsym $mod+Shift+g exec --no-startup-id i3-assign-workspace-to-group

# Select workspace to focus on
bindsym $mod+w exec --no-startup-id i3-focus-on-workspace

# Move the focused container to another workspace
bindsym $mod+Shift+w exec --no-startup-id i3-move-to-workspace

# Rename/renumber workspace. Uses Super+Alt+n
bindsym Mod1+Mod4+n exec --no-startup-id i3-rename-workspace

bindsym $mod+1 $exec_i3_groups workspace-number 1
bindsym $mod+2 $exec_i3_groups workspace-number 2
bindsym $mod+3 $exec_i3_groups workspace-number 3
bindsym $mod+4 $exec_i3_groups workspace-number 4
bindsym $mod+5 $exec_i3_groups workspace-number 5
bindsym $mod+6 $exec_i3_groups workspace-number 6
bindsym $mod+7 $exec_i3_groups workspace-number 7
bindsym $mod+8 $exec_i3_groups workspace-number 8
bindsym $mod+9 $exec_i3_groups workspace-number 9
bindsym $mod+0 $exec_i3_groups workspace-number 10

bindsym $mod+Shift+1 $exec_i3_groups move-to-number 1
bindsym $mod+Shift+2 $exec_i3_groups move-to-number 2
bindsym $mod+Shift+3 $exec_i3_groups move-to-number 3
bindsym $mod+Shift+4 $exec_i3_groups move-to-number 4
bindsym $mod+Shift+5 $exec_i3_groups move-to-number 5
bindsym $mod+Shift+6 $exec_i3_groups move-to-number 6
bindsym $mod+Shift+7 $exec_i3_groups move-to-number 7
bindsym $mod+Shift+8 $exec_i3_groups move-to-number 8
bindsym $mod+Shift+9 $exec_i3_groups move-to-number 9
bindsym $mod+Shift+0 $exec_i3_groups move-to-number 10

# Switch to previous/next workspace (in all groups).
bindsym $mod+p workspace prev
bindsym $mod+n workspace next

bar {
  strip_workspace_numbers yes
  # The rest of your bar config goes below.
  # ...
}
```

### i3-workspace-groups

i3-workspace-groups has an optional config file located at
`$XDG_CONFIG_HOME/i3-workspace-groups/config.toml` (defaults to
`~/.config/i3-workspace-groups/config.toml`). See the
[default config file](./i3wsgroups/default_config.toml) for all the possible
options to configure, their meaning, and their default values.

## Usage

The main operations the CLI tool `i3-workspace-groups` supports are:

- Assign the focused workspace to a group with a given name (and creating the
  group if it doesn't exist).
- Switch the currently [active group](#active-group). Note that the active group
  is not necessarily the same as the [focused group](#focused-group).
- Navigation and movement within a group while ignoring the other groups. See
  examples below.

The tools provided use i3 workspace names to store and read the group for each
workspace. For example, if a user assigns the workspace `mail` to the group
`work`, it will be renamed to `work:mail`.

### Example walk through

> **NOTE:** This walk through assumes that you configured keybindings like the
> [example i3 config](#i3).

Say we start with the following workspace names:

1. `1` with cat videos from YouTube.
2. `2` with a news reader.
3. `3` with a photo editor.
4. `4` with an email client for work.

An important thing to understand here is that every i3 workspace is always
assigned to a single group. And since we haven't assigned any workspace to a
group yet, all the workspaces are implicitly in the
[default group](#default-group), which is denoted as `<default>`.

After a few hours of leisure time, you decide to do some work, which requires
opening a few windows on a few workspaces. In order to create a new group, first
you switch to the workspace `4`, and then you press `Super+Shift+g`, which will
prompt you for a group to assign to the current workspace. You type `work` and
press enter. Since there's no group named `work` yet, the tool will create it
and assign the focused workspace to it. You will then notice that the workspace
name will change in i3bar to `work:4`. Then, you press `Super+g` in order to
switch the [active group](#active-group). You will be shown a list of existing
groups, which will now be `work` and `<default>`. You should now see your
workspaces in i3bar ordered as following: `work:4`, `1`, `2`, `3`. What happened
here? When you switched to the `work` group, the first thing that the tool did
was to move all the workspaces in the work group (only `work:mail`) to be in the
beginning of the workspace list. Then, it renamed the workspaces in the default
group to include the group name, so that they can be differentiated from other
workspaces in the `work` group with the same name.

Then, you decide that you want to open a new terminal window in a new workspace.
So you press `Super+2`, which will move you to a new workspace named `work:2`.
Note that although there is already a workspace with the name `2` in the default
group (now shown as `2` in the workspace list), using `Super+2` actually takes
you to a new empty workspace in the group `work`.

After some time working, you become lazy and you want to get back to cat videos,
but you promise yourself to get back to work in a few hours, and you don't want
to lose your open windows. So you press `Super+g` to switch the active work back
to the default one. You should now see your workspaces in i3bar ordered as
following: `1`, `2`, `3`, `work:4`. The focus will also shift to the first
workspace in the default group (`1` in this case). Now that you're back in the
default group, pressing `Super+2` will again lead you to the workspace `2` in
the default group.

## Concepts

### Active workspace

The active workspace is the workspace with the lowest number. Typically, this
will be the workspace that appears first in the workspace list in i3bar (the
leftmost one).

> **NOTE:** In a multi-monitor setup, there is an active workspace per monitor.
>
> **NOTE:** The active workspace is not necessarily the focused workspace.

### Active group

The active group is the group of the [active workspace](#active-workspace). This
group will normally contain workspaces related to the task you're doing at the
time it's active. When you want to work on another task, you can switch the
active group. Workspaces that are not in the active group can still be
interacted with, but some commands provided are designed to make it easier to
interact with the workspaces of the active group.

> **NOTE:** In a multi-monitor setup, there is an active group per monitor.

### Focused group

The group of the focused workspace.

### Default group

The group of workspaces that were not assigned to a group by the user. This
group is displayed as `<default>`. When you start using i3-workspace-groups,
none of your current workspaces will be assigned to a group yet, so they will
all be in the default group.

## Limitations

- **Interaction with other i3 tools**: workspace names are used for storing the
  group, so if another tool changes a workspace name without preserving the
  format that i3-workspace-groups uses, i3-workspace-groups can make a mistake
  about the group assignment.
- ~~**Latency**: there can be noticeable latency in some machines for the script
  commands. On my high performance desktop this is not noticeable, but on my
  laptop it is. I measured the latency of commands to be around 100-200 ms, most
  of it coming from importing python libraries, so it's not possible to reduce
  it much without running it as a daemon (which will overcomplicate things). In
  the long term, I plan to rewrite it in go.~~ **UPDATE**: there is a new
  experimental client/server mode which significantly reduces latency.
  Documentation is still WIP (see
  <https://github.com/infokiller/i3-workspace-groups/issues/52>).
- **Number of monitors/groups/workspaces**: Supports up to 10 monitors, each
  containing up to 100 groups, each containing up to 100 workspaces.

### Sway compatibility

This project depends on [i3ipc](https://github.com/acrisci/i3ipc-python) for its
interaction with i3, so should also work the same on sway. That said, I don't
test it on sway and i3 is my main window manager.

### Polybar

The official `internal/i3` module does not support workspace groups.

In order to display workspace information in polybar, there are two steps:

1. Add the custom i3 workspace groups module to your polybar
2. Run a script in the background to update polybar's display whenever an i3
   window event occurs

#### 1. Add the custom i3 workspace groups module to your polybar config

Create an `i3-mod` module by adding the following to your polybar config:

```
[module/i3-mod]
type = custom/ipc
hook-0 = ${env:I3_MOD_HOOK}
initial = 1
```

Then, add the `i3-mod` module to your modules:

```
modules-center = i3-mod
```

Then, when launching polybar, do something like the following to configure the
`I3_MOD_HOOK`:

```bash
while IFS='' read -r monitor; do
    i3_mod_hook="i3-workspace-groups polybar-hook --monitor '${monitor}'"
    I3_MOD_HOOK="${i3_mod_hook}" polybar your-bar-name &
done < <(polybar --list-monitors | cut -d':' -f1)
```

#### 2. Run a background script to update polybar's on i3 events

Run the
[polybar_module_updater.py](./i3wsgroups/polybar_module_updater.py)
script. This script is responsible for calling the hook to update polybar
whenever a relevant i3 window event occurs.
