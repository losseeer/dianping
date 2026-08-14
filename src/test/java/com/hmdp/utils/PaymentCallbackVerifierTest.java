package com.hmdp.utils;

import org.junit.jupiter.api.Test;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PaymentCallbackVerifierTest {

    private static final String SECRET = "test-callback-secret";

    private final PaymentCallbackVerifier verifier = new PaymentCallbackVerifier(SECRET);

    @Test
    void acceptsValidPaySignatureAndRejectsTamperedAmount() throws Exception {
        String signature = sign("PAY\ntrade-1\n1001\n5000");

        assertTrue(verifier.verifyPay(signature, "trade-1", 1001L, 5000L));
        assertFalse(verifier.verifyPay(signature, "trade-1", 1001L, 5001L));
    }

    @Test
    void rejectsCallbacksWhenSecretIsNotConfigured() {
        PaymentCallbackVerifier disabled = new PaymentCallbackVerifier("");
        assertFalse(disabled.verifyRefund("00", "trade-1", 1001L, 5000L));
    }

    @Test
    void acceptsValidRefundSignature() throws Exception {
        String signature = sign("REFUND\ntrade-1\n1001\n5000");
        assertTrue(verifier.verifyRefund(signature, "trade-1", 1001L, 5000L));
    }

    private String sign(String payload) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(SECRET.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        StringBuilder result = new StringBuilder();
        for (byte value : mac.doFinal(payload.getBytes(StandardCharsets.UTF_8))) {
            result.append(String.format("%02x", value & 0xff));
        }
        return result.toString();
    }
}
