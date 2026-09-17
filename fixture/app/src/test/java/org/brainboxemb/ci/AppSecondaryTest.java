package org.brainboxemb.ci;

import org.junit.Test;
import static org.junit.Assert.assertTrue;

public class AppSecondaryTest {
    @Test
    public void messageContainsSeparator() {
        assertTrue(App.message().contains("+"));
    }
}
