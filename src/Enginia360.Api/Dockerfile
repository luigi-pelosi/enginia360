FROM mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24@sha256:230c3fbae0ceedc70bca04eed2bfb5694e8b248cadbb81010f41b7a993601f55 AS build
WORKDIR /source
COPY Directory.Build.props global.json ./
COPY src/Enginia360.Api/ src/Enginia360.Api/
RUN dotnet restore src/Enginia360.Api --locked-mode
RUN dotnet publish src/Enginia360.Api -c Release --no-restore -o /app /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0.13-alpine3.24@sha256:819bd3649d8bf53f35527c68d62e17b348ef6f24ae73073f497f00a878348062
WORKDIR /app
COPY --from=build /app ./
USER $APP_UID
ENV ASPNETCORE_HTTP_PORTS=8080 DOTNET_EnableDiagnostics=0 ASPNETCORE_ENVIRONMENT=Production
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/health/ready || exit 1
ENTRYPOINT ["dotnet", "Enginia360.Api.dll"]
