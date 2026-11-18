FROM mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 AS build
WORKDIR /src
COPY Enginia360.Api.csproj packages.lock.json ./
RUN dotnet restore --locked-mode --disable-parallel
COPY . .
RUN dotnet publish -c Release --no-restore -o /out /p:UseSharedCompilation=false /m:1

# Il digest della base runtime viene fissato dall'integratore.
FROM mcr.microsoft.com/dotnet/aspnet:10.0-alpine3.24@sha256:486297ae006e95ee2ee3112a2c03e3d26e41fbbc64b7a29e28e7a18cc36b12bb AS runtime
WORKDIR /app
COPY --from=build /out .
USER root
RUN mkdir -p /app/keys && chown -R app:app /app
USER app
ENV ASPNETCORE_URLS=http://+:8080 DOTNET_EnableDiagnostics=0
EXPOSE 8080
ENTRYPOINT ["dotnet", "Enginia360.Api.dll"]
