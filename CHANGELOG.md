# Changelog

## [0.3.0](https://github.com/Solierrr/google-registry/compare/v0.2.0...v0.3.0) (2026-10-02)


### Features

* add address, llm keys and timezone capabilities and make the registry stateless ([#21](https://github.com/Solierrr/google-registry/issues/21)) ([982545b](https://github.com/Solierrr/google-registry/commit/982545bbd6abc8f908d02f2279fe1f85d4b41781))

## [0.2.0](https://github.com/Solierrr/google-registry/compare/v0.1.0...v0.2.0) (2026-09-30)


### Features

* add app package skeleton and settings ([#8](https://github.com/Solierrr/google-registry/issues/8)) ([de16cad](https://github.com/Solierrr/google-registry/commit/de16cad9e401068e3812b60306b0058c37e22c3b))
* add domain exception hierarchy and handlers ([#9](https://github.com/Solierrr/google-registry/issues/9)) ([2495e16](https://github.com/Solierrr/google-registry/commit/2495e161e179f3c54aee9905f5eda02bb96f6c2a))
* add i18n translation capability ([5fc27eb](https://github.com/Solierrr/google-registry/commit/5fc27eb0fac14e6b612866b74d7cf95f0a101574))
* add jwt bearer authentication against api-auth jwks ([#13](https://github.com/Solierrr/google-registry/issues/13)) ([a199918](https://github.com/Solierrr/google-registry/commit/a1999189603454eaa48da6fd67c770339be493e9))
* add opentelemetry logging, metrics and tracing setup ([#10](https://github.com/Solierrr/google-registry/issues/10)) ([88ca878](https://github.com/Solierrr/google-registry/commit/88ca8782741eaa0b1f2cb39b260c7dd68a7703a2))
* add resilient google http client ([#12](https://github.com/Solierrr/google-registry/issues/12)) ([d2a13e1](https://github.com/Solierrr/google-registry/commit/d2a13e11f8a2d31c01df73f77480dc3229aca001))
* self-bootstrap infra-scripts and split env flow into vault-config, vault-auth, extract-env ([a6e6ff1](https://github.com/Solierrr/google-registry/commit/a6e6ff12b2f09441447ad4a9b8200a4ef7ebb592))


### Bug Fixes

* add missing fastapi entrypoint and fix broken dockerfile ([b3dfea5](https://github.com/Solierrr/google-registry/commit/b3dfea532c5362bb40e7e69e1d689e8931e34b87))
* grant pull-requests write permission to release workflow ([70fcd0f](https://github.com/Solierrr/google-registry/commit/70fcd0f3797d78e157c7eca9fbbe4baad51fb2d0))
* pass vault arguments correctly in PowerShell ([51c0769](https://github.com/Solierrr/google-registry/commit/51c0769d182aa2f5c2974a620c85f6a196c04e0f))
* support powershell secret extraction ([1a07637](https://github.com/Solierrr/google-registry/commit/1a07637bba5bd5a33bf61d4a6e4f474121d87792))
* trigger releases by command ([4b3c084](https://github.com/Solierrr/google-registry/commit/4b3c08497d622e3a3d53080da1a733a3c5551229))
