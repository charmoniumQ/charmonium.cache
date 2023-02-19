{
  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        name = "main";
        extensions = "yaml_metadata_block+citations";
      in
      {
        packages.${name} = pkgs.stdenv.mkDerivation {
          inherit name;
          src = ./.;
          installPhase = ''
mkdir $out
            ${pkgs.pandoc}/bin/pandoc --resource-path=$src/resources $src/${name}.md --from=markdown+${extensions} --to=pdf --citeproc --output=$out/${name}.pdf
          '';
          buildInputs = [
            pkgs.pandoc
            (
              pkgs.texlive.combine {
                inherit (pkgs.texlive)
                  scheme-basic
                  xcolor
                ;
              }
            )
          ];
        };
        defaultPackage = self.packages.${system}.${name};
      });
}
