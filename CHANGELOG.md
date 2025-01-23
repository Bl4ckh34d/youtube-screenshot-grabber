# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New "Only Sunrise" capture mode option
- More comprehensive logging of settings and capture times
- Improved settings synchronization between components
- Documentation for silent startup using Start-Silent.vbs

### Changed
- Replaced binary sunset toggle with three-state capture mode selection (Both/Sunrise/Sunset)
- Enhanced logging format for better readability
- Made scheduler use shared settings object for better state management

### Removed
- Deprecated toggle_only_sunsets code in favor of new capture mode system
