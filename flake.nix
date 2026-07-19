{
  description = "scarlet-applesilicon development environment";

  nixConfig = {
    extra-substituters = [ "https://scarlet-rust-toolchain.cachix.org" ];
    extra-trusted-public-keys = [
      "scarlet-rust-toolchain.cachix.org-1:p+coBExi0nNTIvWF/oM9H9/1/GhwFtqGZ2Vs+4pYl6o="
    ];
  };

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    scarlet-rust-toolchain.url = "github:petitstrawberry/scarlet-rust-nix";
    scarlet-sdk = {
      url = "github:petitstrawberry/scarlet-sdk";
      flake = false;
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      scarlet-rust-toolchain,
      scarlet-sdk,
    }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs supportedSystems (system: f system);

    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          rustToolchain = scarlet-rust-toolchain.packages.${system}.scarlet-rust-toolchain;

          cargo-scarlet = pkgs.rustPlatform.buildRustPackage {
            pname = "cargo-scarlet";
            version = "0.1.0";
            src = scarlet-sdk;
            buildAndTestSubdir = "cargo-scarlet";
            cargoLock.lockFile = "${scarlet-sdk}/Cargo.lock";
          };

          cargo-scarlet-plugin-limine = pkgs.rustPlatform.buildRustPackage {
            pname = "cargo-scarlet-plugin-limine";
            version = "0.1.0";
            src = scarlet-sdk;
            buildAndTestSubdir = "cargo-scarlet-plugin-limine";
            cargoLock.lockFile = "${scarlet-sdk}/Cargo.lock";
          };

        in
        {
          default = pkgs.mkShell {
            packages = [
              cargo-scarlet
              cargo-scarlet-plugin-limine
              pkgs.qemu
              pkgs.git
              pkgs.curl
              pkgs.gnumake
            ];
            hardeningDisable = [ "zerocallusedregs" ];
            shellHook = ''
              export PATH="${rustToolchain}/bin:$PATH"
              export SCARLET_RUST_ACTIVE_BIN="${rustToolchain}/bin"
            '';
          };
        }
      );
    };
}
