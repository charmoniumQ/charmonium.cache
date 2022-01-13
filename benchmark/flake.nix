{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs";
  inputs.flake-utils.url = "github:numtide/flake-utils";
  # inputs.poetry2nix.url = "github:nix-community/poetry2nix";
  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        name = "charmonium-determ-hash";
        name-shell = "${name}-shell";
        name-test = "${name}-test";
        default-python = pkgs.python39;
        # Alternative Pythons for Tox
        alternative-pythons = [
          pkgs.python39
        ];
        poetry2nix-crypto-override = pkgs.poetry2nix.overrides.withDefaults (self: super: {
          cryptography = super.cryptography.overridePythonAttrs(old: {
            cargoDeps = pkgs.rustPlatform.fetchCargoTarball {
              inherit (old) src;
              name = "${old.pname}-${old.version}";
              sourceRoot = "${old.pname}-${old.version}/src/rust/";
              sha256 = "sha256-kozYXkqt1Wpqyo9GYCwN08J+zV92ZWFJY/f+rulxmeQ=";
            };
            cargoRoot = "src/rust";
            nativeBuildInputs = old.nativeBuildInputs ++ (with pkgs.rustPlatform; [
              rust.rustc
              rust.cargo
              cargoSetupHook
            ]);
          });
        });
      in {
        packages.${name} = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          python = default-python;
          overrides = poetry2nix-crypto-override;
        };
        packages.${name-shell} = pkgs.mkShell {
          buildInputs = alternative-pythons ++ [
            default-python
            pkgs.git
            pkgs.poetry
            # pkgs.micromamba
            pkgs.conda
            pkgs.libxml2
            pkgs.libxslt
            pkgs.postgresql
            (pkgs.poetry2nix.mkPoetryEnv {
              projectDir = ./.;
              # default Python for shell
              python = default-python;
              overrides = poetry2nix-crypto-override;
            })
          ];
        };
        devShell = self.packages.${system}.${name-shell};
        defaultPackage = self.packages.${system}.${name};
      });
}
