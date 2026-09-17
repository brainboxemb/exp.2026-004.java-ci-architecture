package org.brainboxemb.ci;

public final class FeatureB {
    private FeatureB() {}

    public static String value() {
        return Core.value() + "-b";
    }
}
