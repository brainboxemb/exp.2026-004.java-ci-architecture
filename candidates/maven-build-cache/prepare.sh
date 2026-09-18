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

cat > .mvn/maven-build-cache-config.xml <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<cache xmlns="http://maven.apache.org/BUILD-CACHE-CONFIG/1.4.0"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:schemaLocation="http://maven.apache.org/BUILD-CACHE-CONFIG/1.4.0 https://maven.apache.org/xsd/build-cache-config-1.4.0.xsd">
  <configuration>
    <attachedOutputs>
      <dirNames>
        <dirName>surefire-reports</dirName>
      </dirNames>
    </attachedOutputs>
  </configuration>
</cache>
EOF

# Resolve and load the core extension before priming/measured lifecycle timing.
# Force dependency metadata refresh so a stale negative Maven resolution marker
# from a restored dependency cache cannot leak into the measured testcase.
# Cache reads/writes are disabled for this preparation invocation itself.
./mvnw --batch-mode --no-transfer-progress -U \
  -Dmaven.build.cache.skipCache=true \
  -Dmaven.build.cache.skipSave=true \
  -DskipTests \
  validate >/dev/null

./mvnw --version >/dev/null
