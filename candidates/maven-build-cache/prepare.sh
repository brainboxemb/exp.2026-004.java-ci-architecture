#!/usr/bin/env bash
set -euo pipefail

mkdir -p .mvn
cat > .mvn/extensions.xml <<'EOF'
<extensions xmlns="http://maven.apache.org/EXTENSIONS/1.1.0"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xsi:schemaLocation="http://maven.apache.org/EXTENSIONS/1.1.0 https://maven.apache.org/xsd/core-extensions-1.1.0.xsd">
  <extension>
    <groupId>org.apache.maven.extensions</groupId>
    <artifactId>maven-build-cache-extension</artifactId>
    <version>1.3.0</version>
  </extension>
</extensions>
EOF

# Resolve/load the core extension before the priming/measured lifecycle timings.
./mvnw --version >/dev/null
