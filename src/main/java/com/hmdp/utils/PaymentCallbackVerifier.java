package com.hmdp.utils;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

@Component
public class PaymentCallbackVerifier {

    private static final String HMAC_SHA_256 = "HmacSHA256";

    private final byte[] secret;

    public PaymentCallbackVerifier(@Value("${payment.callback-secret:}") String secret) {
        this.secret = secret == null ? new byte[0] : secret.getBytes(StandardCharsets.UTF_8);
    }

    public boolean verifyPay(String signature, String tradeNo, Long orderId, Long amount) {
        return verify(signature, payload("PAY", tradeNo, orderId, amount));
    }

    public boolean verifyRefund(String signature, String tradeNo, Long orderId, Long amount) {
        return verify(signature, payload("REFUND", tradeNo, orderId, amount));
    }

    private String payload(String event, String tradeNo, Long orderId, Long amount) {
        return event + "\n" + tradeNo + "\n" + orderId + "\n" + (amount == null ? "" : amount);
    }

    private boolean verify(String signature, String payload) {
        if (secret.length == 0 || signature == null || signature.length() != 64) {
            return false;
        }
        try {
            Mac mac = Mac.getInstance(HMAC_SHA_256);
            mac.init(new SecretKeySpec(secret, HMAC_SHA_256));
            byte[] expected = mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));
            byte[] actual = decodeHex(signature);
            return actual != null && MessageDigest.isEqual(expected, actual);
        } catch (Exception e) {
            return false;
        }
    }

    private byte[] decodeHex(String value) {
        byte[] result = new byte[value.length() / 2];
        for (int i = 0; i < value.length(); i += 2) {
            int high = Character.digit(value.charAt(i), 16);
            int low = Character.digit(value.charAt(i + 1), 16);
            if (high < 0 || low < 0) {
                return null;
            }
            result[i / 2] = (byte) ((high << 4) + low);
        }
        return result;
    }
}
