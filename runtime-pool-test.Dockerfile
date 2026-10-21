FROM mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24@sha256:230c3fbae0ceedc70bca04eed2bfb5694e8b248cadbb81010f41b7a993601f55
WORKDIR /source
COPY Directory.Build.props ./
COPY src/ ./src/
COPY tests/ ./tests/
RUN dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet build tests/Enginia360.Api.Tests -c Release --no-restore
ENV HOME=/tmp DOTNET_CLI_HOME=/tmp
USER 1654:1654
ENTRYPOINT ["dotnet", "test", "tests/Enginia360.Api.Tests", "-c", "Release", "--no-build", "--no-restore", "--filter", "FullyQualifiedName~RuntimeMigrationPoolTests", "--results-directory", "/tmp/results"]
