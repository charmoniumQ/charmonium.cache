{
  inputs = {
    flake-utils = {
      url = "github:numtide/flake-utils";
    };
    nixpkgs = {
      url = "github:NixOS/nixpkgs";
    };
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs = {
        nixpkgs = {
          follows = "nixpkgs";
        };
      };
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        p2n = poetry2nix.legacyPackages.${system};
        pyproject = builtins.fromTOML(builtins.readFile(./pyproject.toml));
        name = pyproject.tool.poetry.name;
        default-python = pkgs.python310;
        # Alternative Pythons for Tox
        alternative-pythons = [
          pkgs.python38
          pkgs.python39
          pkgs.python310
        ];
        dev-dependencies = [
          pkgs.poetry
        ];
        pypkgs-build-requirements = {
          charmonium-cache = [ "poetry" ];
          charmonium-time-block = [ "poetry" ];
          charmonium-async-subprocess = [ "poetry" ];
          charmonium-freeze = [ "poetry" ];
          tox = [ "hatchling" "hatch-vcs" ];
          bump2version = [ "setuptools" ];
          gitchangelog = [ "setuptools" "d2to1" ];
          mando = [ "setuptools" ];
          proselint = [ "poetry" ];
          deptry = [ "poetry" ];
          pyproject-api = [ "hatchling" "hatch-vcs" ];
          pyprojroot = [ "setuptools" ];
          autoimport = [ "setuptools" ];
          radon = [ "setuptools" ];
          pytest-assume = [ "setuptools" ];
        };
        p2n-overrides = p2n.defaultPoetryOverrides.extend (self: super:
          builtins.mapAttrs (package: build-requirements:
            (builtins.getAttr package super).overridePythonAttrs (old: {
              buildInputs = (old.buildInputs or [ ]) ++ (builtins.map (pkg: if builtins.isString pkg then builtins.getAttr pkg super else pkg) build-requirements);
            })
          ) pypkgs-build-requirements
        );
      in {
        devShells = rec {
          default = pkgs.mkShell {
            packages = [
              (p2n.mkPoetryEnv {
                projectDir = ./.;
                python = default-python;
                groups = [ "dev" ];
                overrides = p2n-overrides;
              })
            ] ++ dev-dependencies ++ alternative-pythons;
          };
        };
      });
}
