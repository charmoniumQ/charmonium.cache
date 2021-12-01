{
  inputs.flake-utils.url = "github:numtide/flake-utils";
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
      in {
        packages.${name} = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          python = default-python;
        };
        packages.${name-shell} = pkgs.mkShell {
          buildInputs = alternative-pythons ++ [
            default-python
            pkgs.git
            pkgs.poetry
            pkgs.micromamba
            pkgs.conda
            # (pkgs.poetry2nix.mkPoetryEnv {
            #   projectDir = ./.;
            #   # default Python for shell
            #   python = default-python;
            # })
          ];
          shellHook = ''
            export LD_LIBRARY_PATH=${pkgs.stdenv.cc.cc.lib}/lib
          '';
        };
        devShell = self.packages.${system}.${name-shell};
        defaultPackage = self.packages.${system}.${name};
      });
}
