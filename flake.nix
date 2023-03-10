{
  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pyproject = builtins.fromTOML(builtins.readFile(./pyproject.toml));
        name = pyproject.tool.poetry.name;
        name-pure-shell = "${name}-pure-shell";
        name-shell = "${name}-shell";
        name-test = "${name}-test";
        default-python = pkgs.python310;
        # Alternative Pythons for Tox
        alternative-pythons = [
          pkgs.python38
          pkgs.python39
          pkgs.python310
        ];
      in {
        packages.${name} = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          python = default-python;
        };

        # There are two approaches to make a poetry project work in Nix:
        # 1. Use Nix to install dependencies in poetry.lock.
        # 2. Use Nix to install Poetry and use Poetry to install dependencies in poetry.lock.
        # Option 2 is less elegant, because it uses a package manager to install a package manager.
        # For example, to effectively cache the environment in CI, I have to cache the Nix state and the Poetry venv.
        # But at the time of writing poetry2nix DOES NOT WORK with Python's cryptography.
        # Cryptography is a core dependency, so it won't work at all.
        # ${name-pure-shell} is option 1, ${name-shell} is option 2.
        packages.${name-pure-shell} = pkgs.mkShell {
          buildInputs = alternative-pythons ++ [
            pkgs.poetry
            (pkgs.poetry2nix.mkPoetryEnv {
              projectDir = ./.;
              # default Python for shell
              python = default-python;
            })
          ];
          # TODO: write a check expression (`nix flake check`)
        };

        packages.${name-shell} = pkgs.mkShell {
          buildInputs = alternative-pythons ++ [
            pkgs.poetry
          ];
          shellHook = ''
            if [ ! -f poetry.lock ] || [ ! -f build/poetry-$(sha1sum poetry.lock | cut -f1 -d' ') ]; then
                poetry install --remove-untracked
                rm -rf build
                mkdir build
                touch build/poetry-$(sha1sum poetry.lock | cut -f1 -d' ')
            fi
            export PREPEND_TO_PS1="(${name}) "
            export PYTHONNOUSERSITE=true
            export VIRTUAL_ENV=$(poetry env info -p)
            export PATH=$VIRTUAL_ENV/bin:$PATH
            #export LD_LIBRARY_PATH=LD_LIBRARY_PATH=${pkgs.libseccomp.lib}/lib:${pkgs.gcc-unwrapped.lib}/lib:$LD_LIBRARY_PATH
          '';
          # TODO: write a check expression (`nix flake check`)
        };

        devShell = self.packages.${system}.${name-shell};

        defaultPackage = self.packages.${system}.${name};
      });
}
