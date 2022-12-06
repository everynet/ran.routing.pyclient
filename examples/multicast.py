from ran.routing.core import Core


async def main():
    # Some constants
    dev_eui = 0xFFFFFFFFFFFFFFFF
    dev_addr = 0xFFFFFFFF
    multicast_addr = 0xEEEEEEEE
    multicast_addr_2 = 0xCCCCCCCC

    async with Core(access_token="...", url="...") as ran:
        # Creating device, which we will add into multicast group
        dev = await ran.routing_table.insert(dev_eui=dev_eui, dev_addr=dev_addr)
        print("Created device:\n", repr(dev), end="\n\n")
        assert dev.dev_eui == dev_eui

        # Creating multicast group
        mc = await ran.multicast_groups.create_multicast_group("test", multicast_addr)
        print("New shiny multicast group:\n", repr(mc), end="\n\n")
        assert mc.addr == multicast_addr

        # Adding device to multicast group
        assert await ran.multicast_groups.add_device_to_multicast_group(mc.addr, dev.dev_eui) is True

        # Gathering multicast groups info
        mcg = await ran.multicast_groups.get_multicast_groups()
        print("Multicast group with added device:\n", mcg, end="\n\n")
        assert mcg[0].devices == [dev_eui]

        # Removing device from multicast group
        assert await ran.multicast_groups.remove_device_from_multicast_group(mc.addr, dev.dev_eui) is True

        # Check, is device not in this group anymore
        mcg = await ran.multicast_groups.get_multicast_groups()
        print("Multicast group device removed:\n", mcg, end="\n\n")
        assert mcg[0].devices == []

        # Updating multicast group
        mc = await ran.multicast_groups.update_multicast_group(
            addr=multicast_addr, new_name="test2", new_addr=multicast_addr_2
        )
        print("Multicast group after update:\n", repr(mc), end="\n\n")
        assert mc.addr == multicast_addr_2

        assert await ran.multicast_groups.delete_multicast_groups([multicast_addr_2]) == 1
        assert await ran.routing_table.delete([dev_eui]) == 1


if __name__ == "__main__":
    import asyncio

    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
