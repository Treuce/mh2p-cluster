package de.audi.app.car.adi.legacy.sportchrono;

import de.audi.atip.log.LogChannel;
import org.osgi.framework.BundleContext;

/**
 * No-op stand-in for the Porsche PCM5 class of the same name.
 *
 * The mod's AndroidAuto2Subsystem constructs this class and the cluster
 * integration calls mountStorageRW() before writing logs to a USB stick or SD
 * card. Audi MH2p HMIs do not ship the "Sport Chrono" package, so without a
 * stand-in the shadowed subsystem dies with NoClassDefFoundError and Android
 * Auto stops working. This class satisfies the three members the mod uses and
 * does nothing; external logging then simply falls back to /tmp when the
 * media is mounted read-only.
 *
 * Built by modkit/stub/build_stub.sh to class-file version 48 (Java 1.4), the
 * format the head unit's JVM accepts. Packaged only into the Audi JARs by
 * modkit/build_sd_package.sh; the Porsche package is unchanged.
 */
public class StorageMountHandler {

    public StorageMountHandler(BundleContext context, LogChannel logChannel) {
    }

    public void init() {
    }

    public void mountStorageRW(String mountPoint) {
    }
}
