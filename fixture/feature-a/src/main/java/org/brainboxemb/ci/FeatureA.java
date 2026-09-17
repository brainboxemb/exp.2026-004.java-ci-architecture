package org.brainboxemb.ci;

public final class FeatureA {
    private FeatureA() {}

    public static String value() {
        return Core.value() + "-a";
    }
}
