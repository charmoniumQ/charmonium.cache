{
  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        name = "charmonium-cache";
        name-shell = "${name}-shell";
      in
        {
          packages.${name} = pkgs.poetry2nix.mkPoetryApplication {
            projectDir = ./.;
          };
          packages.${name-shell} = pkgs.mkShell {
            buildInputs = [
              pkgs.python37
              pkgs.python38
              pkgs.python39
              pkgs.python310
              pkgs.poetry
              pkgs.nodePackages.pyright
            ];
            shellHook = ''
              # create venv if it doesn't exist
              poetry run true

              export VIRTUAL_ENV=$(poetry env info --path)
              export POETRY_ACTIVE=1
              source "$VIRTUAL_ENV/bin/activate"
            '';
          };
          devShell = self.packages.${system}.${name-shell};
          defaultPackage = self.packages.${system}.${name};
          defaultApp = self.packages.${system}.${name};
        }
    );
}
