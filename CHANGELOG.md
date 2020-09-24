# Changelog for i3-workspace-groups

## 0.4.7

- Add `--no-auto-back-and-forth` option to `workspace-number` and `move-to-number` commands.

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
