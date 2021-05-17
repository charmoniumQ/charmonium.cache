# save this as shell.nix
{ pkgs ? import <nixpkgs> {}}:

pkgs.mkShell {
  nativeBuildInputs = [
    pkgs.python310
    pkgs.poetry
    pkgs.nodePackages.pyright
  ];
}
