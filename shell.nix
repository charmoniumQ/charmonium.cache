{ pkgs ? import <nixpkgs> {}}:

# pkgs.poetry2nix.mkPoetryEnv {
#     projectDir = ./.;
#     # python = pkgs.python310;
#     # editablePackageSources = {
#     #   "charmonium.cache" = ./charmonium/cache;
#     # };
# }

pkgs.mkShell {
  nativeBuildInputs = [
    pkgs.python37
    pkgs.python38
    pkgs.python39
    pkgs.poetry
    pkgs.nodePackages.pyright
    pkgs.python
  ];
  shellHook = ''
    # create venv if it doesn't exist
    poetry run true

    export VIRTUAL_ENV=$(poetry env info --path)
    export POETRY_ACTIVE=1
    path=$(basename $PWD)
    source "$VIRTUAL_ENV/bin/activate"
  '';
}
