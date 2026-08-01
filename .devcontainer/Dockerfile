FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# The base image contains an old Yarn apt source whose signing key is no longer
# available. Remove it before the Docker feature runs apt-get update.
RUN find /etc/apt -type f \( -name "*.list" -o -name "*.sources" \) \
    -exec sed -i "/dl\\.yarnpkg\\.com/d" {} +
