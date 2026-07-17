# Java JWT RS256 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the shared-secret `JwtUtil` with an RS256 issuer/verifier split so only `auth-center` can sign tokens and business services can only verify them.

**Architecture:** `auth-center` owns `JwtTokenIssuer` and its PKCS#8 private key. `base-security` owns `JwtTokenVerifier`, a `kid`-indexed X.509 public-key set, typed verified claims, and Bearer header parsing. All JWTs require RS256, `kid`, Issuer, Audience, expiry, `jti`, and an explicit Access/Refresh type.

**Tech Stack:** Java 21, Spring Boot 3, Maven 3.8.6, JJWT 0.12.5, JUnit 5, Mockito, Spring Boot configuration properties.

## Global Constraints

- Work in `/Users/mia/Desktop/dev/code/case/java-base-module` on branch `codex/security-rs256-p0`, created from local `develop`.
- Do not use or retain a shared HMAC secret, a working default key, or a production-compilable legacy `JwtUtil` example.
- Use RS256 explicitly; reject every other `alg` value.
- Require RSA keys of at least 2048 bits.
- Private-key configuration exists only in `server/auth-center`; business services receive only public keys.
- Token lifetimes continue to come only from `ClientType`.
- Never log complete, masked, prefixed, hashed, or partially decoded Token/key material.
- Real Nacos configuration is not modified by this plan. Repository files contain property placeholders only.
- Every production-code change follows RED → GREEN → REFACTOR and ends in its own commit.
- Run Maven through `/Users/mia/Documents/apache-maven-3.8.6/bin/mvn` with `-Drevision=1.0`.

---

## File Map

### `base-security` public verification boundary

- Create `common/base-security/src/main/java/com/xiwen/security/jwt/JwtTokenType.java`: Access/Refresh enum.
- Create `common/base-security/src/main/java/com/xiwen/security/jwt/VerifiedJwtClaims.java`: immutable verified identity data.
- Create `common/base-security/src/main/java/com/xiwen/security/jwt/JwtVerificationException.java`: sanitized verification failure.
- Create `common/base-security/src/main/java/com/xiwen/security/jwt/JwtTokenVerifier.java`: typed verification interface.
- Create `common/base-security/src/main/java/com/xiwen/security/jwt/BearerTokenResolver.java`: Authorization header adapter.
- Create `common/base-security/src/main/java/com/xiwen/security/jwt/config/JwtVerifierProperties.java`: shared verifier configuration.
- Create `common/base-security/src/main/java/com/xiwen/security/jwt/key/RsaPublicKeySet.java`: Base64/X.509 parsing and `kid` lookup.
- Create `common/base-security/src/main/java/com/xiwen/security/jwt/RsaJwtTokenVerifier.java`: RS256 JJWT verification.
- Create `common/base-security/src/main/java/com/xiwen/security/config/JwtCryptoAutoConfiguration.java`: verifier beans.
- Modify `common/base-security/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`: load crypto configuration before security configuration.

### `auth-center` private signing boundary

- Create `server/auth-center/src/main/java/com/xiwen/server/auth/jwt/JwtIssuerProperties.java`: active `kid` and private key.
- Create `server/auth-center/src/main/java/com/xiwen/server/auth/jwt/JwtTokenIssuer.java`: signing interface.
- Create `server/auth-center/src/main/java/com/xiwen/server/auth/jwt/RsaPrivateKeyMaterial.java`: PKCS#8 parsing and public/private pair validation.
- Create `server/auth-center/src/main/java/com/xiwen/server/auth/jwt/RsaJwtTokenIssuer.java`: RS256 token creation.
- Create `server/auth-center/src/main/java/com/xiwen/server/auth/jwt/JwtIssuerConfiguration.java`: issuer beans.

### Callers and cleanup

- Modify `common/base-security/src/main/java/com/xiwen/security/filter/JwtAuthenticationFilter.java`.
- Modify `common/base-security/src/main/java/com/xiwen/security/interceptor/AbstractAuthInterceptor.java`.
- Modify `common/base-security/src/main/java/com/xiwen/security/service/LocalJwtSecurityAuthProvider.java`.
- Modify `common/base-security/src/main/java/com/xiwen/security/config/BaseSecurityAutoConfiguration.java`.
- Modify `server/admin/src/main/java/com/xiwen/server/admin/config/AdminSecurityConfig.java`.
- Modify `server/education/src/main/java/com/xiwen/server/education/config/EducationSecurityConfig.java`.
- Modify `server/im/src/main/java/com/xiwen/server/im/websocket/WebSocketAuthInterceptor.java`.
- Modify `server/auth-center/src/main/java/com/xiwen/server/auth/service/AuthService.java`.
- Modify `server/auth-center/src/main/java/com/xiwen/server/auth/service/TokenService.java`.
- Modify `server/auth-center/src/main/java/com/xiwen/server/user/controller/inner/InnerPermissionValidationController.java`.
- Modify `server/auth-center/src/main/java/com/xiwen/server/auth/service/impl/IUserTokenServiceImpl.java`.
- Modify `server/admin/src/main/java/com/xiwen/server/admin/controller/AdminAuthController.java`.
- Delete `common/base-security/src/main/java/com/xiwen/security/jwt/JwtUtil.java` after every caller is migrated.
- Modify `docs/yaml/base.yaml` and `docs/yaml/auth-center.yaml`.
- Create `docs/security/jwt-rs256-nacos.md`.

---

### Task 1: Establish Typed Verification Configuration and RSA Public-Key Set

**Files:**
- Create: `common/base-security/src/main/java/com/xiwen/security/jwt/JwtTokenType.java`
- Create: `common/base-security/src/main/java/com/xiwen/security/jwt/VerifiedJwtClaims.java`
- Create: `common/base-security/src/main/java/com/xiwen/security/jwt/JwtVerificationException.java`
- Create: `common/base-security/src/main/java/com/xiwen/security/jwt/JwtTokenVerifier.java`
- Create: `common/base-security/src/main/java/com/xiwen/security/jwt/config/JwtVerifierProperties.java`
- Create: `common/base-security/src/main/java/com/xiwen/security/jwt/key/RsaPublicKeySet.java`
- Test: `common/base-security/src/test/java/com/xiwen/security/jwt/config/JwtVerifierPropertiesTest.java`
- Test: `common/base-security/src/test/java/com/xiwen/security/jwt/key/RsaPublicKeySetTest.java`
- Test support: `common/base-security/src/test/java/com/xiwen/security/jwt/RsaJwtTestFixtures.java`

**Interfaces:**
- Produces: `VerifiedJwtClaims JwtTokenVerifier.verifyAccessToken(String rawToken)`.
- Produces: `VerifiedJwtClaims JwtTokenVerifier.verifyRefreshToken(String rawToken)`.
- Produces: `RSAPublicKey RsaPublicKeySet.require(String keyId)`.
- Produces: `JwtVerifierProperties(String issuer, String audience, Map<String, String> publicKeys)`.

- [ ] **Step 1: Write failing configuration and key tests**

Use a test-only RSA generator so no fixed key material enters Git:

```java
public final class RsaJwtTestFixtures {
    private RsaJwtTestFixtures() {}

    public static KeyPair keyPair() {
        try {
            KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
            generator.initialize(2048);
            return generator.generateKeyPair();
        } catch (GeneralSecurityException exception) {
            throw new IllegalStateException(exception);
        }
    }

    public static String publicKey(KeyPair pair) {
        return Base64.getEncoder().encodeToString(pair.getPublic().getEncoded());
    }

    public static String privateKey(KeyPair pair) {
        return Base64.getEncoder().encodeToString(pair.getPrivate().getEncoded());
    }
}
```

The tests must assert these exact cases:

```java
assertThrows(IllegalArgumentException.class,
        () -> new JwtVerifierProperties("", "xiwen-services", Map.of("key-1", "value")));
assertThrows(IllegalArgumentException.class,
        () -> new JwtVerifierProperties("xiwen-auth-center", "", Map.of("key-1", "value")));
assertThrows(IllegalArgumentException.class,
        () -> new JwtVerifierProperties("xiwen-auth-center", "xiwen-services", Map.of()));

KeyPair pair = RsaJwtTestFixtures.keyPair();
JwtVerifierProperties properties = new JwtVerifierProperties(
        "xiwen-auth-center", "xiwen-services",
        Map.of("key-1", RsaJwtTestFixtures.publicKey(pair)));
RsaPublicKeySet keySet = RsaPublicKeySet.from(properties);
assertEquals(pair.getPublic(), keySet.require("key-1"));
assertThrows(JwtVerificationException.class, () -> keySet.require("unknown"));
```

Also cover invalid Base64, non-X.509 bytes, a non-RSA public key, RSA smaller than 2048 bits, blank `kid`, and an exception message that does not contain the configured Base64 value.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
/Users/mia/Documents/apache-maven-3.8.6/bin/mvn -pl common/base-security -am \
  -Dtest=JwtVerifierPropertiesTest,RsaPublicKeySetTest \
  -Dsurefire.failIfNoSpecifiedTests=false test -Drevision=1.0
```

Expected: compilation fails because the new contracts and key set do not exist.

- [ ] **Step 3: Implement the minimal typed contracts**

Use these exact public shapes:

```java
public enum JwtTokenType {
    ACCESS, REFRESH
}

public record VerifiedJwtClaims(
        String tokenId,
        Long userId,
        String username,
        ClientType clientType,
        JwtTokenType tokenType,
        Instant issuedAt,
        Instant expiresAt,
        String issuer,
        Set<String> audience,
        String keyId) {
}

public interface JwtTokenVerifier {
    VerifiedJwtClaims verifyAccessToken(String rawToken);
    VerifiedJwtClaims verifyRefreshToken(String rawToken);
}

public class JwtVerificationException extends RuntimeException {
    public JwtVerificationException(String message) { super(message); }
    public JwtVerificationException(String message, Throwable cause) { super(message, cause); }
}
```

`JwtVerifierProperties` must trim and reject blank Issuer/Audience, copy the public-key map with `Map.copyOf`, and reject blank `kid` or blank encoded key values. `RsaPublicKeySet.from` must Base64-decode each value, parse `X509EncodedKeySpec` through `KeyFactory.getInstance("RSA")`, cast to `RSAPublicKey`, require `getModulus().bitLength() >= 2048`, and store an immutable map. Its exception messages may include only the property path and `kid`.

- [ ] **Step 4: Run tests to verify GREEN**

Run the Step 2 command again.

Expected: all `JwtVerifierPropertiesTest` and `RsaPublicKeySetTest` cases pass.

- [ ] **Step 5: Commit**

```bash
git add -- \
  common/base-security/src/main/java/com/xiwen/security/jwt/JwtTokenType.java \
  common/base-security/src/main/java/com/xiwen/security/jwt/VerifiedJwtClaims.java \
  common/base-security/src/main/java/com/xiwen/security/jwt/JwtVerificationException.java \
  common/base-security/src/main/java/com/xiwen/security/jwt/JwtTokenVerifier.java \
  common/base-security/src/main/java/com/xiwen/security/jwt/config/JwtVerifierProperties.java \
  common/base-security/src/main/java/com/xiwen/security/jwt/key/RsaPublicKeySet.java \
  common/base-security/src/test/java/com/xiwen/security/jwt/RsaJwtTestFixtures.java \
  common/base-security/src/test/java/com/xiwen/security/jwt/config/JwtVerifierPropertiesTest.java \
  common/base-security/src/test/java/com/xiwen/security/jwt/key/RsaPublicKeySetTest.java
git commit -m "feat(security): 建立 JWT 公钥配置契约"
```

### Task 2: Implement RS256 Verification and Bearer Resolution

**Files:**
- Create: `common/base-security/src/main/java/com/xiwen/security/jwt/BearerTokenResolver.java`
- Create: `common/base-security/src/main/java/com/xiwen/security/jwt/RsaJwtTokenVerifier.java`
- Create: `common/base-security/src/main/java/com/xiwen/security/config/JwtCryptoAutoConfiguration.java`
- Modify: `common/base-security/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`
- Test: `common/base-security/src/test/java/com/xiwen/security/jwt/BearerTokenResolverTest.java`
- Test: `common/base-security/src/test/java/com/xiwen/security/jwt/RsaJwtTokenVerifierTest.java`
- Test: `common/base-security/src/test/java/com/xiwen/security/config/JwtCryptoAutoConfigurationTest.java`

**Interfaces:**
- Consumes: `JwtVerifierProperties`, `RsaPublicKeySet`, and the Task 1 verification contracts.
- Produces: Spring beans `JwtTokenVerifier` and `BearerTokenResolver`.

- [ ] **Step 1: Write failing Bearer and verifier tests**

Bearer cases:

```java
BearerTokenResolver resolver = new BearerTokenResolver();
assertEquals("raw-token", resolver.resolve("Bearer raw-token"));
assertEquals("raw-token", resolver.resolve("bearer   raw-token"));
assertThrows(JwtVerificationException.class, () -> resolver.resolve(null));
assertThrows(JwtVerificationException.class, () -> resolver.resolve("Basic abc"));
assertThrows(JwtVerificationException.class, () -> resolver.resolve("Bearer   "));
```

Create test JWTs with JJWT and a generated RSA key. Assert:

```java
VerifiedJwtClaims claims = verifier.verifyAccessToken(accessToken);
assertEquals(42L, claims.userId());
assertEquals("alice", claims.username());
assertEquals(ClientType.WEB, claims.clientType());
assertEquals(JwtTokenType.ACCESS, claims.tokenType());
assertEquals("key-1", claims.keyId());
```

Add explicit rejection tests for unknown `kid`, HS256, a second RSA public key, expired Token, wrong Issuer, wrong Audience, Refresh Token through `verifyAccessToken`, Access Token through `verifyRefreshToken`, missing `jti`, missing `iat`, missing username, invalid client type, and `sub`/userId mismatch.

- [ ] **Step 2: Run tests to verify RED**

```bash
/Users/mia/Documents/apache-maven-3.8.6/bin/mvn -pl common/base-security -am \
  -Dtest=BearerTokenResolverTest,RsaJwtTokenVerifierTest,JwtCryptoAutoConfigurationTest \
  -Dsurefire.failIfNoSpecifiedTests=false test -Drevision=1.0
```

Expected: compilation fails because the resolver, verifier and auto-configuration do not exist.

- [ ] **Step 3: Implement strict parsing and one-pass verification**

`BearerTokenResolver.resolve` must locate the first ASCII space, compare the scheme with `equalsIgnoreCase("Bearer")`, trim credentials, and throw sanitized `JwtVerificationException` messages.

Build one immutable JJWT parser in `RsaJwtTokenVerifier`:

```java
this.parser = Jwts.parser()
        .keyLocator(new LocatorAdapter<Key>() {
            @Override
            protected Key locate(JwsHeader header) {
                if (!"RS256".equals(header.getAlgorithm())) {
                    throw new JwtVerificationException("JWT algorithm must be RS256");
                }
                return publicKeys.require(header.getKeyId());
            }
        })
        .requireIssuer(properties.issuer())
        .requireAudience(properties.audience())
        .sig().clear().add(Jwts.SIG.RS256).and()
        .build();
```

Both public verify methods call one private `verify(String, JwtTokenType)` method. It must call `parseSignedClaims` exactly once, validate all required Claim values, convert `clientType` with `ClientType.valueOf`, compare `subject` with `userId.toString()`, and wrap JJWT/runtime failures in `JwtVerificationException("JWT verification failed")` without copying the Token or cause message.

`JwtCryptoAutoConfiguration` must use `@EnableConfigurationProperties(JwtVerifierProperties.class)` and expose:

```java
@Bean RsaPublicKeySet rsaPublicKeySet(JwtVerifierProperties properties)
@Bean JwtTokenVerifier jwtTokenVerifier(JwtVerifierProperties properties, RsaPublicKeySet keys)
@Bean BearerTokenResolver bearerTokenResolver()
```

Register it before `BaseSecurityAutoConfiguration` in `AutoConfiguration.imports`.

- [ ] **Step 4: Run tests and module regression**

Run the Step 2 command, then:

```bash
/Users/mia/Documents/apache-maven-3.8.6/bin/mvn -pl common/base-security -am test -Drevision=1.0
```

Expected: new tests pass and all existing `base-security` tests remain green.

- [ ] **Step 5: Commit**

```bash
git add -- \
  common/base-security/src/main/java/com/xiwen/security/jwt/BearerTokenResolver.java \
  common/base-security/src/main/java/com/xiwen/security/jwt/RsaJwtTokenVerifier.java \
  common/base-security/src/main/java/com/xiwen/security/config/JwtCryptoAutoConfiguration.java \
  common/base-security/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports \
  common/base-security/src/test/java/com/xiwen/security/jwt/BearerTokenResolverTest.java \
  common/base-security/src/test/java/com/xiwen/security/jwt/RsaJwtTokenVerifierTest.java \
  common/base-security/src/test/java/com/xiwen/security/config/JwtCryptoAutoConfigurationTest.java
git commit -m "feat(security): 实现 RS256 公钥验签"
```

### Task 3: Add the Auth-Center-Only RS256 Issuer

**Files:**
- Create: `server/auth-center/src/main/java/com/xiwen/server/auth/jwt/JwtIssuerProperties.java`
- Create: `server/auth-center/src/main/java/com/xiwen/server/auth/jwt/JwtTokenIssuer.java`
- Create: `server/auth-center/src/main/java/com/xiwen/server/auth/jwt/RsaPrivateKeyMaterial.java`
- Create: `server/auth-center/src/main/java/com/xiwen/server/auth/jwt/RsaJwtTokenIssuer.java`
- Create: `server/auth-center/src/main/java/com/xiwen/server/auth/jwt/JwtIssuerConfiguration.java`
- Test: `server/auth-center/src/test/java/com/xiwen/server/auth/jwt/RsaPrivateKeyMaterialTest.java`
- Test: `server/auth-center/src/test/java/com/xiwen/server/auth/jwt/RsaJwtTokenIssuerTest.java`

**Interfaces:**
- Consumes: `JwtVerifierProperties`, `RsaPublicKeySet`, `JwtTokenVerifier`, `ClientType`.
- Produces: `String JwtTokenIssuer.issueAccessToken(Long userId, String username, ClientType clientType)`.
- Produces: `String JwtTokenIssuer.issueRefreshToken(Long userId, String username, ClientType clientType)`.

- [ ] **Step 1: Write failing issuer tests**

Use a generated test KeyPair. Assert invalid Base64, non-PKCS#8 bytes, RSA below 2048 bits, missing active `kid`, and mismatched private/public keys fail without leaking encoded values.

For a valid issuer:

```java
String access = issuer.issueAccessToken(42L, "alice", ClientType.WEB);
String refresh = issuer.issueRefreshToken(42L, "alice", ClientType.WEB);

VerifiedJwtClaims accessClaims = verifier.verifyAccessToken(access);
VerifiedJwtClaims refreshClaims = verifier.verifyRefreshToken(refresh);
assertEquals(JwtTokenType.ACCESS, accessClaims.tokenType());
assertEquals(JwtTokenType.REFRESH, refreshClaims.tokenType());
assertNotEquals(accessClaims.tokenId(), refreshClaims.tokenId());
assertEquals("key-1", accessClaims.keyId());
```

Decode only the test Token header and assert `alg=RS256`, `typ=JWT`, and `kid=key-1`. Assert Access and Refresh expiry deltas match `ClientType.WEB` within a two-second tolerance.

- [ ] **Step 2: Run tests to verify RED**

```bash
/Users/mia/Documents/apache-maven-3.8.6/bin/mvn -pl server/auth-center -am \
  -Dtest=RsaPrivateKeyMaterialTest,RsaJwtTokenIssuerTest \
  -Dsurefire.failIfNoSpecifiedTests=false test -Drevision=1.0
```

Expected: compilation fails because issuer classes do not exist.

- [ ] **Step 3: Implement issuer properties, key validation and signing**

Use these signatures:

```java
public record JwtIssuerProperties(String activeKeyId, String privateKey) { }

public interface JwtTokenIssuer {
    String issueAccessToken(Long userId, String username, ClientType clientType);
    String issueRefreshToken(Long userId, String username, ClientType clientType);
}
```

`RsaPrivateKeyMaterial.from` must Base64-decode PKCS#8, parse `RSAPrivateKey`, require 2048 bits, require the active public key, and prove the pair by signing fixed bytes with `SHA256withRSA` and verifying them with the selected public key.

The shared issuer method must construct tokens as follows:

```java
return Jwts.builder()
        .header().type("JWT").keyId(properties.activeKeyId()).and()
        .issuer(verifierProperties.issuer())
        .audience().add(verifierProperties.audience()).and()
        .subject(userId.toString())
        .id(UUID.randomUUID().toString())
        .issuedAt(Date.from(now))
        .expiration(Date.from(now.plusSeconds(expirationSeconds)))
        .claim("userId", userId)
        .claim("username", username)
        .claim("clientType", clientType.name())
        .claim("tokenType", tokenType.name())
        .signWith(privateKey, Jwts.SIG.RS256)
        .compact();
```

`JwtIssuerConfiguration` uses `@EnableConfigurationProperties(JwtIssuerProperties.class)` and creates issuer key material and `JwtTokenIssuer`. It remains under `server/auth-center` so business modules cannot depend on the signing API.

- [ ] **Step 4: Run tests and auth-center regression**

Run the Step 2 command, then:

```bash
/Users/mia/Documents/apache-maven-3.8.6/bin/mvn -pl server/auth-center -am test -Drevision=1.0
```

Expected: issuer tests pass and the auth-center dependency reactor is green.

- [ ] **Step 5: Commit**

```bash
git add -- server/auth-center/src/main/java/com/xiwen/server/auth/jwt \
  server/auth-center/src/test/java/com/xiwen/server/auth/jwt
git commit -m "feat(auth): 使用 RS256 私钥签发 JWT"
```

### Task 4: Migrate Base Security and Business-Service Verification

**Files:**
- Modify: `common/base-security/src/main/java/com/xiwen/security/filter/JwtAuthenticationFilter.java`
- Modify: `common/base-security/src/main/java/com/xiwen/security/interceptor/AbstractAuthInterceptor.java`
- Modify: `common/base-security/src/main/java/com/xiwen/security/service/LocalJwtSecurityAuthProvider.java`
- Modify: `common/base-security/src/main/java/com/xiwen/security/config/BaseSecurityAutoConfiguration.java`
- Modify tests under `common/base-security/src/test/java/com/xiwen/security/filter`, `interceptor`, and `service`.
- Modify: `server/admin/src/main/java/com/xiwen/server/admin/config/AdminSecurityConfig.java`
- Modify: `server/education/src/main/java/com/xiwen/server/education/config/EducationSecurityConfig.java`
- Modify: `server/im/src/main/java/com/xiwen/server/im/websocket/WebSocketAuthInterceptor.java`
- Test: `server/im/src/test/java/com/xiwen/server/im/websocket/WebSocketAuthInterceptorTest.java`

**Interfaces:**
- Consumes: `BearerTokenResolver`, `JwtTokenVerifier`, `VerifiedJwtClaims`.
- Preserves: `Long SecurityAuthProvider.validateToken(String rawToken)` for filter compatibility.

- [ ] **Step 1: Rewrite tests against the verifier contract before production code**

Update `LocalJwtSecurityAuthProviderTest` to mock `JwtTokenVerifier`:

```java
when(verifier.verifyAccessToken("raw-token")).thenReturn(verifiedClaims(42L));
assertEquals(42L, provider.validateToken("raw-token"));
verify(verifier).verifyAccessToken("raw-token");
```

Update filter/interceptor tests to inject a real `BearerTokenResolver`. Add WebSocket tests asserting a valid Access Token stores userId/username but not the raw Token in handshake attributes, and a verification exception returns `false`.

- [ ] **Step 2: Run tests to verify RED**

```bash
/Users/mia/Documents/apache-maven-3.8.6/bin/mvn \
  -pl common/base-security,server/admin,server/education,server/im -am \
  -Dtest=LocalJwtSecurityAuthProviderTest,JwtAuthenticationFilterTokenContractTest,AbstractAuthInterceptorTokenContractTest,WebSocketAuthInterceptorTest \
  -Dsurefire.failIfNoSpecifiedTests=false test -Drevision=1.0
```

Expected: compilation fails while production constructors still require `JwtUtil` or do not accept `BearerTokenResolver`.

- [ ] **Step 3: Migrate production callers**

`LocalJwtSecurityAuthProvider.validateToken` becomes:

```java
try {
    return verifier.verifyAccessToken(rawToken).userId();
} catch (JwtVerificationException exception) {
    return null;
}
```

`JwtAuthenticationFilter` and `AbstractAuthInterceptor` must delegate Authorization parsing to the injected `BearerTokenResolver`; remove their duplicate private parsing methods. `BaseSecurityAutoConfiguration` injects the resolver when constructing the filter.

Admin and Education `securityAuthProvider` beans accept `JwtTokenVerifier` instead of `JwtUtil`. WebSocket verification calls `verifyAccessToken`, stores only `userId`, `username`, and `conversationId`, and removes `attributes.put("token", token)`.

- [ ] **Step 4: Run security/business regression**

Run the Step 2 command, then:

```bash
/Users/mia/Documents/apache-maven-3.8.6/bin/mvn \
  -pl common/base-security,server/admin,server/education,server/im -am test -Drevision=1.0
```

Expected: all selected module tests pass.

- [ ] **Step 5: Commit**

```bash
git add -- \
  common/base-security/src/main/java/com/xiwen/security/filter/JwtAuthenticationFilter.java \
  common/base-security/src/main/java/com/xiwen/security/interceptor/AbstractAuthInterceptor.java \
  common/base-security/src/main/java/com/xiwen/security/service/LocalJwtSecurityAuthProvider.java \
  common/base-security/src/main/java/com/xiwen/security/config/BaseSecurityAutoConfiguration.java \
  common/base-security/src/test/java/com/xiwen/security \
  server/admin/src/main/java/com/xiwen/server/admin/config/AdminSecurityConfig.java \
  server/education/src/main/java/com/xiwen/server/education/config/EducationSecurityConfig.java \
  server/im/src/main/java/com/xiwen/server/im/websocket/WebSocketAuthInterceptor.java \
  server/im/src/test/java/com/xiwen/server/im/websocket/WebSocketAuthInterceptorTest.java
git commit -m "refactor(security): 迁移业务服务 RS256 验签"
```

### Task 5: Migrate Auth-Center Login, Refresh, Renewal, Logout and Validation

**Files:**
- Modify: `server/auth-center/src/main/java/com/xiwen/server/auth/service/AuthService.java`
- Modify: `server/auth-center/src/main/java/com/xiwen/server/auth/service/TokenService.java`
- Modify: `server/auth-center/src/main/java/com/xiwen/server/user/controller/inner/InnerPermissionValidationController.java`
- Test: `server/auth-center/src/test/java/com/xiwen/server/auth/service/AuthServiceJwtContractTest.java`
- Test: `server/auth-center/src/test/java/com/xiwen/server/auth/service/TokenServiceJwtContractTest.java`
- Test: `server/auth-center/src/test/java/com/xiwen/server/user/controller/inner/InnerPermissionValidationControllerJwtTest.java`

**Interfaces:**
- Consumes: `JwtTokenIssuer`, `JwtTokenVerifier`, `BearerTokenResolver`, `VerifiedJwtClaims`.
- Preserves public service and Feign method signatures.

- [ ] **Step 1: Add caller contract tests**

Mock collaborators and assert:

```java
when(issuer.issueAccessToken(42L, "alice", ClientType.WEB)).thenReturn("new-access");
when(issuer.issueRefreshToken(42L, "alice", ClientType.WEB)).thenReturn("new-refresh");
```

Login must call both issuer methods. Refresh must call `verifyRefreshToken` and never `verifyAccessToken`. Logout, validate and renewal must resolve Bearer once and call `verifyAccessToken`. `InnerPermissionValidationController` must resolve the header and return `verifyAccessToken(raw).userId()` without logging the input.

For Token expiration persistence, provide `VerifiedJwtClaims.expiresAt()` and assert the exact `LocalDateTime` written to `UserToken`. For blacklist TTL, fix a test clock/expiry and assert `max(0, Duration.between(now, expiresAt).getSeconds())`.

- [ ] **Step 2: Run tests to verify RED**

```bash
/Users/mia/Documents/apache-maven-3.8.6/bin/mvn -pl server/auth-center -am \
  -Dtest=AuthServiceJwtContractTest,TokenServiceJwtContractTest,InnerPermissionValidationControllerJwtTest \
  -Dsurefire.failIfNoSpecifiedTests=false test -Drevision=1.0
```

Expected: compilation fails or Mockito verification fails because services still depend on `JwtUtil`.

- [ ] **Step 3: Replace each `JwtUtil` operation with typed contracts**

Use this mapping exactly:

| Old call | New call |
|---|---|
| `generateAccessToken` | `issuer.issueAccessToken` |
| `generateRefreshToken` | `issuer.issueRefreshToken` |
| `extractTokenFromHeader` | `bearerTokenResolver.resolve` |
| `validateToken` + `extract*` | one `verifier.verifyAccessToken` or `verifyRefreshToken` |
| `getExpirationDateTime` | `LocalDateTime.ofInstant(claims.expiresAt(), ZoneId.systemDefault())` |
| `getRemainingSeconds` | `Math.max(0, Duration.between(Instant.now(), claims.expiresAt()).getSeconds())` |
| `needsRenewal` | compare remaining seconds with `clientType.getAccessTokenExpiresInSeconds() / 3` |

`TokenService.refreshToken` must reject Access Token input by using only `verifyRefreshToken`. Convert the returned typed `ClientType` directly; do not call `valueOf` on unverified strings. Keep the existing database presence check and current behavior of retaining the Refresh Token.

All verification exceptions crossing a business boundary become the existing generic `BizException` messages without appending `exception.getMessage()`.

- [ ] **Step 4: Run auth-center and security regression**

Run the Step 2 command, then:

```bash
/Users/mia/Documents/apache-maven-3.8.6/bin/mvn \
  -pl common/base-security,server/auth-center -am test -Drevision=1.0
```

Expected: caller tests pass; base-security and auth-center reactors are green.

- [ ] **Step 5: Commit**

```bash
git add -- \
  server/auth-center/src/main/java/com/xiwen/server/auth/service/AuthService.java \
  server/auth-center/src/main/java/com/xiwen/server/auth/service/TokenService.java \
  server/auth-center/src/main/java/com/xiwen/server/user/controller/inner/InnerPermissionValidationController.java \
  server/auth-center/src/test/java/com/xiwen/server/auth/service/AuthServiceJwtContractTest.java \
  server/auth-center/src/test/java/com/xiwen/server/auth/service/TokenServiceJwtContractTest.java \
  server/auth-center/src/test/java/com/xiwen/server/user/controller/inner/InnerPermissionValidationControllerJwtTest.java
git commit -m "refactor(auth): 迁移认证中心 RS256 Token 流程"
```

### Task 6: Remove Sensitive Token Logs, Delete `JwtUtil`, and Document Nacos Configuration

**Files:**
- Modify: `server/admin/src/main/java/com/xiwen/server/admin/controller/AdminAuthController.java`
- Modify: `server/auth-center/src/main/java/com/xiwen/server/auth/service/TokenService.java`
- Modify: `server/auth-center/src/main/java/com/xiwen/server/auth/service/impl/IUserTokenServiceImpl.java`
- Modify: `server/auth-center/src/main/java/com/xiwen/server/user/controller/inner/InnerPermissionValidationController.java`
- Delete: `common/base-security/src/main/java/com/xiwen/security/jwt/JwtUtil.java`
- Modify: `docs/yaml/base.yaml`
- Modify: `docs/yaml/auth-center.yaml`
- Create: `docs/security/jwt-rs256-nacos.md`
- Test: `common/base-security/src/test/java/com/xiwen/security/structure/JwtLegacyRemovalTest.java`

**Interfaces:**
- Removes: `JwtUtil` and all shared-secret properties.
- Documents: verifier public-key configuration and auth-center-only issuer configuration.

- [ ] **Step 1: Add a failing legacy-removal structure test**

The test locates the Java repository root by walking upward from `user.dir` until `common/base-security/pom.xml` exists. Add this helper so checked I/O failures remain visible to JUnit:

```java
private static String read(Path path) {
    return assertDoesNotThrow(() -> Files.readString(path));
}
```

Then assert:

```java
assertFalse(Files.exists(root.resolve(
        "common/base-security/src/main/java/com/xiwen/security/jwt/JwtUtil.java")));

String production;
try (Stream<Path> paths = Files.walk(root)) {
    production = paths
            .filter(path -> path.toString().endsWith(".java"))
            .filter(path -> path.toString().contains("src/main/java"))
            .map(JwtLegacyRemovalTest::read)
            .collect(Collectors.joining("\n"));
}
assertFalse(production.contains("JwtUtil"));
assertFalse(production.contains("jwt.secret"));
```

Add targeted source assertions:

```java
assertFalse(read(root.resolve(
        "server/auth-center/src/main/java/com/xiwen/server/user/controller/inner/InnerPermissionValidationController.java"))
        .contains("log.debug(\"验证Token, token={}\", token)"));
assertFalse(read(root.resolve(
        "server/admin/src/main/java/com/xiwen/server/admin/controller/AdminAuthController.java"))
        .contains("maskToken("));
assertFalse(read(root.resolve(
        "server/auth-center/src/main/java/com/xiwen/server/auth/service/TokenService.java"))
        .contains("accessToken.substring"));
assertFalse(read(root.resolve(
        "server/auth-center/src/main/java/com/xiwen/server/auth/service/impl/IUserTokenServiceImpl.java"))
        .contains("refreshToken.substring"));
```

- [ ] **Step 2: Run test to verify RED**

```bash
/Users/mia/Documents/apache-maven-3.8.6/bin/mvn -pl common/base-security -am \
  -Dtest=JwtLegacyRemovalTest -Dsurefire.failIfNoSpecifiedTests=false test -Drevision=1.0
```

Expected: FAIL because `JwtUtil` and Token-fragment log statements still exist.

- [ ] **Step 3: Remove legacy implementation and sensitive logging**

Delete the old `JwtUtil`. Remove `maskToken` and all Token-valued log arguments from `AdminAuthController`. Replace database query logs with operation-only messages such as `log.debug("查询有效 Access Token 记录")`; remove Bloom-filter Token prefixes and the complete Authorization input log. Keep userId, clientType, operation, result and trace context where available.

Update repository configuration samples:

```yaml
# docs/yaml/base.yaml
jwt:
  verifier:
    issuer: xiwen-auth-center
    audience: xiwen-services
    public-keys:
      key-2026-01: ${JWT_PUBLIC_KEY_2026_01}
```

```yaml
# docs/yaml/auth-center.yaml
jwt:
  issuer:
    active-key-id: key-2026-01
    private-key: ${JWT_PRIVATE_KEY_2026_01}
```

Remove `jwt.secret`, `jwt.access-token-expiration`, and `jwt.refresh-token-expiration` from every repository configuration sample.

`docs/security/jwt-rs256-nacos.md` must document RSA generation, PKCS#8/X.509 Base64 formats, Nacos Data IDs, ACL separation, first migration order, restart-based rotation order, and the fact that old HMAC Tokens become invalid. Use commands that write only to an OS temporary directory:

```bash
mkdir -p /private/tmp/xiwen-jwt-keys
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 \
  -out /private/tmp/xiwen-jwt-keys/private.pem
openssl pkcs8 -topk8 -nocrypt \
  -in /private/tmp/xiwen-jwt-keys/private.pem -outform DER \
  -out /private/tmp/xiwen-jwt-keys/private.der
openssl pkey -in /private/tmp/xiwen-jwt-keys/private.pem -pubout -outform DER \
  -out /private/tmp/xiwen-jwt-keys/public.der
base64 < /private/tmp/xiwen-jwt-keys/private.der
base64 < /private/tmp/xiwen-jwt-keys/public.der
```

The document must tell operators to paste the outputs directly into protected Nacos configuration, clear terminal history if required by local policy, and delete `/private/tmp/xiwen-jwt-keys` after configuration. It must not contain example private-key material.

- [ ] **Step 4: Run removal, module and source checks**

```bash
/Users/mia/Documents/apache-maven-3.8.6/bin/mvn \
  -pl common/base-security,server/auth-center,server/admin,server/education,server/im -am \
  test -Drevision=1.0
rg -n "JwtUtil|jwt\.secret|access-token-expiration|refresh-token-expiration" \
  common server docs --glob '!**/target/**'
rg -n "token.*substring|refreshToken=|token=\{\}|maskToken" \
  common server --glob '*.java' --glob '!**/target/**'
```

Expected: Maven succeeds; both `rg` commands return no production/config matches. Test names and migration documentation may mention `JwtUtil` only inside the removal assertion and historical explanation.

- [ ] **Step 5: Commit**

```bash
git add -- \
  server/admin/src/main/java/com/xiwen/server/admin/controller/AdminAuthController.java \
  server/auth-center/src/main/java/com/xiwen/server/auth/service/TokenService.java \
  server/auth-center/src/main/java/com/xiwen/server/auth/service/impl/IUserTokenServiceImpl.java \
  server/auth-center/src/main/java/com/xiwen/server/user/controller/inner/InnerPermissionValidationController.java \
  common/base-security/src/main/java/com/xiwen/security/jwt/JwtUtil.java \
  common/base-security/src/test/java/com/xiwen/security/structure/JwtLegacyRemovalTest.java \
  docs/yaml/base.yaml docs/yaml/auth-center.yaml docs/security/jwt-rs256-nacos.md
git commit -m "chore(security): 移除共享密钥 JWT 实现"
```

### Task 7: Final Verification and Delivery

**Files:**
- Verify only; do not edit unless a failing check identifies an in-scope defect.

**Interfaces:**
- Confirms all previous tasks integrate into one deployable Java reactor.

- [ ] **Step 1: Run full Maven verification**

```bash
/Users/mia/Documents/apache-maven-3.8.6/bin/mvn test -Drevision=1.0
```

Expected: `BUILD SUCCESS`; all 26 Reactor modules report `SUCCESS`.

- [ ] **Step 2: Verify architecture boundaries and diff hygiene**

```bash
git diff develop...HEAD --check
git status --short
git log --oneline develop..HEAD
rg -n "JwtTokenIssuer|JwtIssuerProperties|private-key" \
  server/admin server/education server/im common/base-security \
  --glob '*.java' --glob '*.yml' --glob '*.yaml' --glob '!**/target/**'
rg -n "Jwts\.SIG\.(HS256|HS384|HS512)|jwt\.secret" \
  common server docs --glob '!**/target/**'
```

Expected: no whitespace errors; clean worktree; six implementation commits; business/common modules have no issuer/private-key matches; no HMAC algorithm or shared-secret configuration remains.

- [ ] **Step 3: Record deployment prerequisites in the handoff**

The final handoff must state:

- Nacos must contain the shared public-key configuration before any business service starts.
- Only `auth-center` may read the private-key Data ID.
- Deploying this version invalidates every old HMAC Access and Refresh Token.
- Services reload keys only on restart in this batch.
- No real Nacos key was generated or changed by the implementation.
