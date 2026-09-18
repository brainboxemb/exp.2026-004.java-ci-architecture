#!/usr/bin/env bash
set -euo pipefail

: "${JAVA_HOME:?JAVA_HOME must identify the Maven runtime JDK}"

release_file="${JAVA_HOME}/release"
wrapper_properties=".mvn/wrapper/maven-wrapper.properties"

if [[ ! -f "${release_file}" ]]; then
  echo "JDK release metadata not found: ${release_file}" >&2
  exit 2
fi
if [[ ! -f "${wrapper_properties}" ]]; then
  echo "Maven wrapper properties not found: ${wrapper_properties}" >&2
  exit 2
fi

runtime_fingerprint="$(
  {
    cat "${release_file}"
    printf '\nrunner.os=%s\nrunner.arch=%s\n' "$(uname -s)" "$(uname -m)"
    printf 'wrapper.sha256='
    sha256sum "${wrapper_properties}" | awk '{print $1}'
    printf '\n'
  } | sha256sum | awk '{print $1}'
)"

cache_base="${MAVEN_BUILD_CACHE_BASE:-${HOME}/.m2/build-cache}"
cache_location="${cache_base%/}/runtime-${runtime_fingerprint}"
mkdir -p "${cache_location}"

exec ./mvnw \
  --batch-mode \
  --no-transfer-progress \
  "-Dmaven.build.cache.location=${cache_location}" \
  "$@"
