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
    macvdmtool-src = {
      url = "github:AsahiLinux/macvdmtool/b22ae51eb43a0e1daa21d41616ac899f28e7bf8a";
      flake = false;
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      scarlet-rust-toolchain,
      scarlet-sdk,
      macvdmtool-src,
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
          pythonEnv = pkgs.python3.withPackages (ps: [
            ps.construct
            ps.pyserial
          ]);

          cargo-scarlet = pkgs.rustPlatform.buildRustPackage {
            pname = "cargo-scarlet";
            version = "0.1.0";
            src = scarlet-sdk;
            buildAndTestSubdir = "cargo-scarlet";
            cargoLock.lockFile = "${scarlet-sdk}/Cargo.lock";
            nativeBuildInputs = [ pkgs.curl ];
          };

          cargo-scarlet-plugin-limine = pkgs.rustPlatform.buildRustPackage {
            pname = "cargo-scarlet-plugin-limine";
            version = "0.1.0";
            src = scarlet-sdk;
            buildAndTestSubdir = "cargo-scarlet-plugin-limine";
            cargoLock.lockFile = "${scarlet-sdk}/Cargo.lock";
          };

          macvdmtool = pkgs.stdenv.mkDerivation {
            pname = "macvdmtool";
            version = "unstable-b22ae51";
            src = macvdmtool-src;

            nativeBuildInputs = [ pkgs.gnumake ];

            installPhase = ''
              runHook preInstall
              install -Dm755 macvdmtool "$out/bin/macvdmtool"
              runHook postInstall
            '';

            meta = {
              description = "Apple Silicon Virtualization.framework companion tool";
              homepage = "https://github.com/AsahiLinux/macvdmtool";
              license = pkgs.lib.licenses.asl20;
              mainProgram = "macvdmtool";
              platforms = [ "aarch64-darwin" ];
            };
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
              pkgs.perl
              pkgs.dtc
              pkgs.e2fsprogs
              pkgs.mtools
              pkgs.gnutar
              pkgs.which
              pkgs.picocom
              pkgs.rsync
              pkgs.tmux
              pkgs.llvmPackages.llvm
              pkgs.clang
              pkgs.lld
              pkgs.pkgsCross.aarch64-multiplatform.buildPackages.gcc
              pythonEnv
            ]
            ++ pkgs.lib.optionals pkgs.stdenv.hostPlatform.isDarwin [ macvdmtool ];
            hardeningDisable = [ "zerocallusedregs" ];
            shellHook = ''
              export PATH="${rustToolchain}/bin:$PATH"
              export SCARLET_RUST_ACTIVE_BIN="${rustToolchain}/bin"
              export CC_aarch64_unknown_scarlet=aarch64-unknown-linux-gnu-gcc
              export AR_aarch64_unknown_scarlet=aarch64-unknown-linux-gnu-ar
              export RANLIB_aarch64_unknown_scarlet=aarch64-unknown-linux-gnu-ranlib
            '';
          };
        }
      );
    };
}
