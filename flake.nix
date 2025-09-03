{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    treefmt-nix.url = "github:numtide/treefmt-nix";
    devshell.url = "github:numtide/devshell";
  };

  outputs =
    inputs@{
      flake-parts,
      nixpkgs,
      ...
    }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" ];
      imports = [
        inputs.treefmt-nix.flakeModule
        inputs.devshell.flakeModule
      ];

      perSystem =
        { pkgs, system, ... }:
        let
          pythonDeps =
            p: with p; [
              scikit-image
              scikit-learn
              scipy
              jupyter
              jupyter-collaboration
              jupytext
              matplotlib
              numpy
              pandas
              plotly
              pytest
              tqdm
              typer
            ];
          app = (pkgs.writeShellApplication {
            name = "berghain";
            text = ''
              export PYTHONPATH=${toString ./.}
              exec ${pkgs.python3}/bin/python -m berghain.cli "$@"
            '';
          }).overrideAttrs { allowSubstitutes = false; };
        in
        {
          _module.args.pkgs = import nixpkgs {
            inherit system;
            config = {
              allowUnfree = true;
              cudaSupport = true;
              cudnnSupoprt = true;
            };
          };

          devshells.default = {
            packages = [
              (pkgs.python3.withPackages pythonDeps)
            ];
          };

          treefmt.config.programs = {
            black.enable = true;
            isort.enable = true;
            nixfmt.enable = true;
          };

          packages.default = app;
          apps.default = {
            type = "app";
            program = "${app}/bin/berghain";
          };
        };
    };
}
