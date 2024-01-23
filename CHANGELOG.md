# Changelog for i3-workspace-groups

## 0.5.0 (pre-release)

## 0.4.7

- Add client/server mode
- Add `workspace-new` command to create a workspace with the first available
  number.
- Add `move-to-new` command to move the focused container to a new workspace
  with the first available number.
- Add `--no-auto-back-and-forth` option to `workspace-number` and
  `move-to-number` commands.
- Add `--use-next-available-number` option to `assign-workspace-to-group`
  command and `use_next_available_number` option to the config file for using
  the first available relative number when assigning or renaming a workspace to
  a group that already has another workspace with that relative number (see #33).

## 0.4.6

- Add configuration file with support for customizing icons

## 0.4.5

- Fix multi monitor issues
- Show monitor name in output of `list-groups` subcommand
- Respect `workspace_auto_back_and_forth` setting (fixes #9)
- Deprecate `workspace-back-and-forth` and `move-to-back-and-forth` now that
  built-in i3 commands should work
- Move group CLI arguments to specific subcommands used
- Support focusing and moving to workspaces that don't exist (fixes #10)
- Support renaming, renumbering, and regrouping workspaces in i3-rename-workspace
