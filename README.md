# i3 Workspace Groups

A Python library and command line tool for managing i3wm workspaces in groups
that you define.
I find this tool useful for managing a large number of workspaces in i3.

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

This has lead me to create the https://github.com/infokiller/i3-workspace-groups
project, which enables you to define and manage groups of workspaces, each with
their own "namespace", and switch between them.

## Overview

The main operations that the CLI tool `i3-workspace-groups` supports are:

- Assign the focused workspace to a group with a given name (and creating the
  group if it doesn't exist).
- Switch the currently [active group](#active-group). Note that the active
  group is not necessarily the same as the [focused group](#focused-group).
- Navigation and movement within a group while ignoring the other groups. See
  examples below.

The tools provided use i3 workspace names to store and read the group for each
workspace. For example, if a user assigns the workspace "mail" to the group
"work", it will be renamed to "mail:word".

### Example walk through

NOTE: This walk through assumes that you configured keybindings like the
[example i3 config](#i3-config).

Say we start with the following workspaces:

1. A workspace named "1" with cat videos from YouTube.
2. A workspace named "2" with a news reader.
2. A workspace named "3" with a photo editor.
2. A workspace named "4" with an email client for work.

An important thing to understand here is that every i3 workspace is always
assigned to a single group. And since we haven't assigned any workspace to a
group yet, all the workspaces are implicitly in the
[default group](#default-group), which is labeled with the string "Ɗ".

After a few hours of leisure time, you decide to do some work, which requires
opening a few windows on a few workspaces. In order to create a new group, first
you switch to the workspace "4", and then you press `Super+Shift+g`, which will
prompt you for a new for the new group. You decide to name it "work" and press
enter. You will then notice that the workspace name will change in i3bar to
"work:4".
Then, you press `Super+g` in order to switch the [active
group](#active-group). You will be shown a list of existing groups, which will
now be "work" and "Ɗ" (for the default group).
You should now see your workspaces in i3bar ordered as following:
"work:4", "Ɗ:1", "Ɗ:2", "Ɗ:3".
What happened here?
When you switched to the "work" group, the first thing that the tool did was to
move all the workspaces in the work group (only "work:email") to be in the
beginning of the workspace list. Then, it renamed the workspaces in the default
group to include the group name, so that they can be
differentiated from other workspaces in the "work" group with the same name.

Then, you decide that you want to open a new terminal window in a new workspace.
So you press `Super+2`, which will move you to a new workspace named "work:2".
Note that although there is already a workspace with the name "2" in the default
group (now shown as "Ɗ:2" in the workspace list), using `Super+2` actually takes
you to a new empty workspace in the group "work".

After some time working, you become lazy and you want to get back to cat videos,
but you promise yourself to get back to work in a few hours, and you don't want
to lose your open winows. So you press `Super+g` to switch the active work back
to the default one. You should now see your workspaces in i3bar ordered as
following: "1", "2", "3", "work:4". The focus will also shift to the first
workspace in the default group ("1" in this case).
Now that you're back in the default group, pressing `Super+2` will again lead
you to the workspace "2" in the default group.

### i3 config

In order to use these tools effectively, commands need to be bound to
keybindings. For example, my i3 config contains the following exerts:

```
set $mod Mod4

strip_workspace_numbers yes

set $exec_i3_groups_tool exec --no-startup-id i3-workspace-groups

# Switch active workspace group
bindcode $mod+g exec --no-startup-id i3-switch-active-workspace-group
# Move workspace to another group
bindcode $mod+Shift+g exec --no-startup-id i3-assign-workspace-to-group

bindsym $mod+1 $exec_i3_groups_tool workspace-number 1
bindsym $mod+2 $exec_i3_groups_tool workspace-number 2
bindsym $mod+3 $exec_i3_groups_tool workspace-number 3
bindsym $mod+4 $exec_i3_groups_tool workspace-number 4
bindsym $mod+5 $exec_i3_groups_tool workspace-number 5
bindsym $mod+6 $exec_i3_groups_tool workspace-number 6
bindsym $mod+7 $exec_i3_groups_tool workspace-number 7
bindsym $mod+8 $exec_i3_groups_tool workspace-number 8
bindsym $mod+9 $exec_i3_groups_tool workspace-number 9
bindsym $mod+0 $exec_i3_groups_tool workspace-number 10

bindsym $mod+Shift+1 $exec_i3_groups_tool move-to-number 1
bindsym $mod+Shift+2 $exec_i3_groups_tool move-to-number 2
bindsym $mod+Shift+3 $exec_i3_groups_tool move-to-number 3
bindsym $mod+Shift+4 $exec_i3_groups_tool move-to-number 4
bindsym $mod+Shift+5 $exec_i3_groups_tool move-to-number 5
bindsym $mod+Shift+6 $exec_i3_groups_tool move-to-number 6
bindsym $mod+Shift+7 $exec_i3_groups_tool move-to-number 7
bindsym $mod+Shift+8 $exec_i3_groups_tool move-to-number 8
bindsym $mod+Shift+9 $exec_i3_groups_tool move-to-number 9
bindsym $mod+Shift+0 $exec_i3_groups_tool move-to-number 10

# Switch to previous workspace in group.
bindcode $mod+p $exec_i3_groups_tool workspace-prev
# Switch to next workspace in group.
bindcode $mod+n $exec_i3_groups_tool workspace-next

# Move to previous workspace in group.
bindcode $mod+Shift+p $exec_i3_groups_tool move-to-prev
# Move to next workspace in group.
bindcode $mod+Shift+n $exec_i3_groups_tool move-to-next
```

I also recommend keeping keybindings for the i3 built in workspace navigation
commands, for example:

```
bindsym $mod+Control+1 workspace number 1
bindsym $mod+Control+2 workspace number 2
bindsym $mod+Control+3 workspace number 3
bindsym $mod+Control+4 workspace number 4
bindsym $mod+Control+5 workspace number 5
bindsym $mod+Control+6 workspace number 6
bindsym $mod+Control+7 workspace number 7
bindsym $mod+Control+8 workspace number 8
bindsym $mod+Control+9 workspace number 9
bindsym $mod+Control+0 workspace number 10
```

### Limitations

- Workspace names are used for storing the group, so if another tool changes a
  workspace name without preserving the format that this project uses, the tool
  can make a mistake about the group assignment.
- Workspace names must not include colons (`:`).
- Group names must not include colons (`:`) or start with a digit.
- Every group can have up to a 100 workspaces by default.

### Definitions

#### Active group

The active workspace is the one that appears first in the workspace list in
i3bar (by default the leftmost one), regardless of whether its focused or not.
The **active group** is the group of the active workspace.
This group will normally contain workspaces related to the task you're doing at
the time it's active. When you want to work on another task, you can switch the
active group.
Workspaces that are not in the active group can still be interacted with, but
some of the commands provided are designed to make it easier to interact with
the workspaces of the active group.

#### Focused group

The group of the focused workspace.

#### Default group

The group of workspaces that were not assigned to a group by the user. This
group is usually displayed as "Ɗ".

## Installation

The scripts can be installed using pip:

```shell
pip install i3-workspace-groups
```

Then you should be able to run the command line tool [`i3-workspace-groups`](scripts/i3-workspace-groups).
There are also two scripts provided that require [rofi](https://github.com/DaveDavenport/rofi):
- [`i3-assign-workspace-to-group`](scripts/i3-assign-workspace-to-group)
- [`i3-switch-active-workspace-group`](scripts/i3-switch-active-workspace-group)

### Sway compatibility note

This project depends on [i3ipc](https://github.com/acrisci/i3ipc-python) for its
interaction with i3, so should also work the same on sway. That said, I didn't
test it yet and i3 is my main window manager.
